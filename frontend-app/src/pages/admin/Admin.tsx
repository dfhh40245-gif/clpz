import { useState, useEffect } from 'react';
import { adminApi, type User, type Job } from '../../lib/api';
import Card from '../../components/ui/Card';
import Button from '../../components/ui/Button';
import Input from '../../components/ui/Input';
import Badge from '../../components/ui/Badge';
import { Users, Activity, Briefcase, Database } from 'lucide-react';

export default function Admin() {
  const [stats, setStats] = useState<Record<string, any>>({});
  const [users, setUsers] = useState<User[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [search, setSearch] = useState('');
  const [selectedUser, setSelectedUser] = useState<{ user: User; txns: any[] } | null>(null);
  const [creditModal, setCreditModal] = useState<{ userId: string; action: 'add' | 'remove' } | null>(null);
  const [creditAmount, setCreditAmount] = useState(1);
  const [creditReason, setCreditReason] = useState('');

  useEffect(() => {
    adminApi.stats().then(setStats).catch(() => {});
    adminApi.users().then(d => setUsers(d.users)).catch(() => {});
    adminApi.jobs().then(d => setJobs(d.jobs)).catch(() => {});
  }, []);

  const searchUsers = async () => {
    if (!search.trim()) { adminApi.users().then(d => setUsers(d.users)); return; }
    adminApi.searchUsers(search).then(d => setUsers(d.users)).catch(() => {});
  };

  const viewUser = async (u: User) => {
    const txns = await adminApi.transactions(u.id).catch(() => ({ transactions: [] }));
    setSelectedUser({ user: u, txns: txns.transactions });
  };

  const confirmCredit = async () => {
    if (!creditModal || !creditAmount) return;
    try {
      if (creditModal.action === 'add') await adminApi.addCredits(creditModal.userId, creditAmount, creditReason || 'Admin adjustment');
      else await adminApi.removeCredits(creditModal.userId, creditAmount, creditReason || 'Admin adjustment');
      setCreditModal(null);
      adminApi.users().then(d => setUsers(d.users));
    } catch (e: any) { alert(e.message); }
  };

  const statCards = [
    { icon: Users, label: 'Users', value: stats.users ?? '-' },
    { icon: Activity, label: 'Sessions', value: stats.sessions ?? '-' },
    { icon: Briefcase, label: 'Jobs', value: stats.jobs ?? '-' },
    { icon: Database, label: 'DB Size', value: stats.db_size_mb ? `${stats.db_size_mb} MB` : '-' },
  ];

  return (
    <div className="max-w-6xl mx-auto px-6 py-8">
      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3.5 mb-8">
        {statCards.map(s => (
          <Card key={s.label} className="p-5">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-clpz-text-tertiary">{s.label}</span>
            <strong className="block mt-2 text-2xl font-bold text-clpz-accent tracking-tight">{s.value}</strong>
          </Card>
        ))}
      </div>

      {/* Users */}
      <Card className="mb-6">
        <div className="flex items-center justify-between p-4 border-b border-clpz-border">
          <h2 className="text-base font-semibold">Users</h2>
          <div className="flex gap-2">
            <Input value={search} onChange={e => setSearch(e.target.value)} onKeyDown={e => e.key === 'Enter' && searchUsers()} placeholder="Search by email…" className="w-48" />
            <Button size="sm" onClick={searchUsers}>Search</Button>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-clpz-border">
                {['Email', 'Credits', 'Verified', 'Joined', 'Actions'].map(h => (
                  <th key={h} className="px-3 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-clpz-text-tertiary">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {users.map(u => (
                <tr key={u.id} className="border-b border-clpz-border hover:bg-white/[0.02]">
                  <td className="px-3 py-2.5 text-sm">{u.email}</td>
                  <td className="px-3 py-2.5 text-sm font-bold">{(u as any).credits ?? 0}</td>
                  <td className="px-3 py-2.5">
                    <Badge variant={u.email_verified ? 'success' : 'warning'}>{u.email_verified ? 'Yes' : 'No'}</Badge>
                  </td>
                  <td className="px-3 py-2.5 text-xs text-clpz-text-secondary">
                    {(u as any).created_at ? new Date((u as any).created_at * 1000).toLocaleDateString() : '-'}
                  </td>
                  <td className="px-3 py-2.5">
                    <div className="flex gap-1.5">
                      <Button size="sm" onClick={() => viewUser(u)}>View</Button>
                      <Button size="sm" onClick={() => setCreditModal({ userId: u.id, action: 'add' })}>+ Add</Button>
                      <Button size="sm" variant="danger" onClick={() => setCreditModal({ userId: u.id, action: 'remove' })}>- Remove</Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {users.length === 0 && <div className="p-8 text-center text-sm text-clpz-text-tertiary">No users found</div>}
        </div>
      </Card>

      {/* User detail */}
      {selectedUser && (
        <Card className="mb-6">
          <div className="flex items-center justify-between p-4 border-b border-clpz-border">
            <h2 className="text-base font-semibold">{selectedUser.user.email}</h2>
            <Button size="sm" variant="ghost" onClick={() => setSelectedUser(null)}>Close</Button>
          </div>
          <div className="p-4 overflow-x-auto">
            <h3 className="text-sm font-semibold mb-3">Transaction History</h3>
            {selectedUser.txns.length === 0 ? (
              <div className="text-sm text-clpz-text-tertiary">No transactions</div>
            ) : (
              <table className="w-full">
                <thead>
                  <tr className="border-b border-clpz-border">
                    {['Date', 'Type', 'Amount', 'Description'].map(h => (
                      <th key={h} className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-clpz-text-tertiary">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {selectedUser.txns.map((t: any, i: number) => (
                    <tr key={i} className="border-b border-clpz-border">
                      <td className="px-3 py-2 text-xs text-clpz-text-secondary">{t.created_at ? new Date(t.created_at * 1000).toLocaleString() : '-'}</td>
                      <td className="px-3 py-2"><Badge>{t.type}</Badge></td>
                      <td className={`px-3 py-2 text-sm font-bold ${t.amount > 0 ? 'text-clpz-success' : 'text-clpz-error'}`}>{t.amount > 0 ? '+' : ''}{t.amount}</td>
                      <td className="px-3 py-2 text-sm text-clpz-text-secondary">{t.description || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </Card>
      )}

      {/* Jobs */}
      <Card>
        <div className="p-4 border-b border-clpz-border">
          <h2 className="text-base font-semibold">Recent Jobs</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-clpz-border">
                {['ID', 'Type', 'Stage', 'Created'].map(h => (
                  <th key={h} className="px-3 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-clpz-text-tertiary">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {jobs.slice(0, 20).map(j => (
                <tr key={j.id} className="border-b border-clpz-border hover:bg-white/[0.02]">
                  <td className="px-3 py-2.5 text-xs font-mono">{j.id.slice(0, 8)}</td>
                  <td className="px-3 py-2.5 text-sm">{j.input_type || '-'}</td>
                  <td className="px-3 py-2.5">
                    <Badge variant={j.stage === 'done' ? 'success' : j.stage === 'error' ? 'error' : 'warning'}>{j.stage}</Badge>
                  </td>
                  <td className="px-3 py-2.5 text-xs text-clpz-text-secondary">
                    {j.created_at ? new Date(j.created_at * 1000).toLocaleString() : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {jobs.length === 0 && <div className="p-8 text-center text-sm text-clpz-text-tertiary">No jobs</div>}
        </div>
      </Card>

      {/* Credit modal */}
      {creditModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm" onClick={() => setCreditModal(null)}>
          <div className="w-[400px] max-w-full p-6 border border-clpz-border rounded-xl bg-clpz-surface-1" onClick={e => e.stopPropagation()}>
            <h3 className="text-base font-semibold mb-4">{creditModal.action === 'add' ? 'Add Credits' : 'Remove Credits'}</h3>
            <div className="space-y-3">
              <Input label="Amount" type="number" min={1} value={creditAmount} onChange={e => setCreditAmount(parseInt(e.target.value) || 0)} />
              <Input label="Reason" value={creditReason} onChange={e => setCreditReason(e.target.value)} placeholder="Reason for adjustment" />
            </div>
            <div className="flex justify-end gap-2 mt-5">
              <Button variant="ghost" onClick={() => setCreditModal(null)}>Cancel</Button>
              <Button onClick={confirmCredit}>Confirm</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
