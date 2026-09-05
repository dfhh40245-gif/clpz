-- CLPZ Supabase Schema
-- Run this in the Supabase SQL editor to set up the database.

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ═══════════════════════════════════════════════════════════════════
-- PROFILES (linked to Supabase Auth users)
-- ═══════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT UNIQUE NOT NULL,
    display_name TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Auto-create profile on signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, email, display_name)
    VALUES (NEW.id, NEW.email, COALESCE(NEW.raw_user_meta_data->>'display_name', ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_new_user();

-- ═══════════════════════════════════════════════════════════════════
-- CREDITS (one row per user)
-- ═══════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS credits (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    balance INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Auto-create credits on profile creation
CREATE OR REPLACE FUNCTION public.handle_new_profile()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.credits (user_id, balance)
    VALUES (NEW.id, 10)
    ON CONFLICT (user_id) DO NOTHING;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE TRIGGER on_profile_created
    AFTER INSERT ON public.profiles
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_new_profile();

-- ═══════════════════════════════════════════════════════════════════
-- CREDIT TRANSACTIONS (immutable audit log)
-- ═══════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS credit_transactions (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    amount INTEGER NOT NULL,
    type TEXT NOT NULL,  -- 'signup_bonus', 'forge', 'refund', 'admin_grant', 'admin_removal'
    reason TEXT DEFAULT '',
    idempotency_key TEXT,
    admin_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_transactions_user ON credit_transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_transactions_idempotency ON credit_transactions(idempotency_key);

-- Prevent duplicate idempotency keys
CREATE UNIQUE INDEX IF NOT EXISTS idx_transactions_idempotency_unique
    ON credit_transactions(idempotency_key)
    WHERE idempotency_key IS NOT NULL AND idempotency_key != '';

-- ═══════════════════════════════════════════════════════════════════
-- JOBS (optional — for web job history)
-- ═══════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS jobs (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    input_type TEXT NOT NULL,  -- 'youtube' or 'upload'
    url TEXT DEFAULT '',
    stage TEXT DEFAULT 'queued',
    progress FLOAT DEFAULT 0,
    max_clips INTEGER DEFAULT 5,
    error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- ═══════════════════════════════════════════════════════════════════
-- ADMIN ROLE (simple boolean on profiles)
-- ═══════════════════════════════════════════════════════════════════
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE;

-- ═══════════════════════════════════════════════════════════════════
-- ROW LEVEL SECURITY
-- ═══════════════════════════════════════════════════════════════════
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE credits ENABLE ROW LEVEL SECURITY;
ALTER TABLE credit_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;

-- Profiles: users can read/update their own
CREATE POLICY "Users can view own profile" ON profiles
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update own profile" ON profiles
    FOR UPDATE USING (auth.uid() = id);

-- Credits: users can read own, but NOT update directly (server-side only)
CREATE POLICY "Users can view own credits" ON credits
    FOR SELECT USING (auth.uid() = user_id);

-- Transactions: users can read own
CREATE POLICY "Users can view own transactions" ON credit_transactions
    FOR SELECT USING (auth.uid() = user_id);

-- Jobs: users can read own
CREATE POLICY "Users can view own jobs" ON jobs
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own jobs" ON jobs
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Admin bypass: service role can do everything
-- (The service role key bypasses RLS by default in Supabase)

-- ═══════════════════════════════════════════════════════════════════
-- RPC: Atomic credit deduction (prevents race conditions)
-- ═══════════════════════════════════════════════════════════════════
CREATE OR REPLACE FUNCTION check_and_deduct_credits(
    p_user_id UUID,
    p_amount INTEGER,
    p_idempotency_key TEXT DEFAULT ''
)
RETURNS TABLE(success BOOLEAN, remaining INTEGER)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    current_balance INTEGER;
    new_balance INTEGER;
BEGIN
    -- Check idempotency
    IF p_idempotency_key != '' THEN
        IF EXISTS (
            SELECT 1 FROM credit_transactions
            WHERE idempotency_key = p_idempotency_key
        ) THEN
            SELECT balance INTO current_balance FROM credits WHERE user_id = p_user_id;
            RETURN QUERY SELECT TRUE, COALESCE(current_balance, 0);
            RETURN;
        END IF;
    END IF;

    -- Get current balance with row lock
    SELECT balance INTO current_balance
    FROM credits WHERE user_id = p_user_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RETURN QUERY SELECT FALSE, 0;
        RETURN;
    END IF;

    IF current_balance < p_amount THEN
        RETURN QUERY SELECT FALSE, current_balance;
        RETURN;
    END IF;

    -- Deduct
    new_balance := current_balance - p_amount;
    UPDATE credits SET balance = new_balance, updated_at = NOW()
    WHERE user_id = p_user_id;

    -- Record transaction
    INSERT INTO credit_transactions (user_id, amount, type, reason, idempotency_key)
    VALUES (p_user_id, -p_amount, 'forge', 'Clip generation', NULLIF(p_idempotency_key, ''));

    RETURN QUERY SELECT TRUE, new_balance;
END;
$$;
