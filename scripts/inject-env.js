const fs = require('fs');
const path = require('path');

const url = process.env.NEXT_PUBLIC_SUPABASE_URL || '';
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '';

if (!url || !anonKey) {
  console.error('Missing NEXT_PUBLIC_SUPABASE_URL or NEXT_PUBLIC_SUPABASE_ANON_KEY.');
  process.exit(1);
}

const config = `// Generated during Vercel build. Do not edit manually.
window.__CLPZ_SUPABASE_URL__ = ${JSON.stringify(url)};
window.__CLPZ_SUPABASE_ANON_KEY__ = ${JSON.stringify(anonKey)};
`;

const output = path.join(__dirname, '..', 'frontend', 'config.js');
fs.writeFileSync(output, config, 'utf8');
console.log('Generated frontend/config.js with Supabase public configuration.');
