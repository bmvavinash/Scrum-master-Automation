import { useQuery } from '@tanstack/react-query'
import { VelocityAPI } from '../lib/api'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend, BarChart, Bar } from 'recharts'

export default function Dashboard() {
  const { data: dashboard = {}, isLoading } = useQuery({
    queryKey: ['velocity', 'dashboard'],
    queryFn: () => VelocityAPI.getDashboard(),
  })

  if (isLoading) return <div>Loading dashboard...</div>

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Dashboard</h1>
      {dashboard?.summary && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard label="Total Sprints" value={dashboard.summary.total_sprints} />
          <StatCard label="Avg Velocity" value={dashboard.summary.average_velocity} />
          <StatCard label="Story Points Completed" value={dashboard.summary.total_story_points_completed} />
          <StatCard label="Avg Cycle Time (days)" value={dashboard.summary.average_cycle_time_days} />
        </div>
      )}

      {/* Velocity per sprint (bar) */}
      {dashboard?.velocity_metrics && dashboard.velocity_metrics.length > 0 && (
        <div className="rounded-lg border bg-white p-4">
          <h2 className="font-medium mb-2">Velocity by Sprint</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={dashboard.velocity_metrics}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="sprint_name" hide={false} interval={0} angle={-15} textAnchor="end" height={60} />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="planned_story_points" name="Planned" fill="#94a3b8" />
                <Bar dataKey="completed_story_points" name="Completed" fill="#3b82f6" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Burndown (line) - use the latest sprint with burndown */}
      {dashboard?.velocity_metrics && dashboard.velocity_metrics[0]?.burndown_data?.length > 0 && (
        <div className="rounded-lg border bg-white p-4">
          <h2 className="font-medium mb-2">Burndown (Latest Sprint)</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={dashboard.velocity_metrics[0].burndown_data}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="remaining_points" name="Remaining" stroke="#ef4444" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="completed_points" name="Completed" stroke="#22c55e" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  )
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border bg-white p-4">
      <div className="text-sm text-gray-500">{label}</div>
      <div className="text-2xl font-semibold">{value ?? 0}</div>
    </div>
  )
}


