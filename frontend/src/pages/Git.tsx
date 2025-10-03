import { useQuery } from '@tanstack/react-query'
import { GitAPI } from '../lib/api'

export default function Git() {
  const { data: commits, isLoading: loadingCommits } = useQuery({ queryKey: ['git','commits'], queryFn: () => GitAPI.dbCommits({ limit: 25 }) })
  const { data: prs, isLoading: loadingPRs } = useQuery({ queryKey: ['git','prs'], queryFn: () => GitAPI.dbPullRequests({ limit: 25 }) })

  const getStatusColor = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'merged': return 'bg-purple-100 text-purple-800'
      case 'open': return 'bg-green-100 text-green-800'
      case 'closed': return 'bg-red-100 text-red-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  const formatDate = (dateString: string) => {
    if (!dateString) return 'Unknown'
    return new Date(dateString).toLocaleDateString()
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Git Activity</h1>
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Commits */}
        <section className="space-y-4">
          <h2 className="text-lg font-semibold text-gray-800">Recent Commits</h2>
          {loadingCommits ? (
            <div className="flex items-center justify-center h-32">
              <div className="text-gray-500">Loading commits...</div>
            </div>
          ) : (
            <div className="space-y-3">
              {(commits || []).map((c: any) => (
                <div key={c.id || c.sha} className="bg-white rounded-lg border border-gray-200 p-4">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="font-medium text-gray-900 mb-1">{c.message}</div>
                      <div className="flex items-center gap-4 text-sm text-gray-500">
                        <span>Author: {c.author}</span>
                        <span>Branch: {c.branch}</span>
                        <span>{formatDate(c.timestamp)}</span>
                      </div>
                      {c.jira_tickets && c.jira_tickets.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1">
                          {c.jira_tickets.map((ticket: string, idx: number) => (
                            <span key={idx} className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded-full">
                              {ticket}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                    <div className="text-xs text-gray-400 font-mono ml-2">
                      {c.sha?.substring(0, 7)}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Pull Requests */}
        <section className="space-y-4">
          <h2 className="text-lg font-semibold text-gray-800">Pull Requests</h2>
          {loadingPRs ? (
            <div className="flex items-center justify-center h-32">
              <div className="text-gray-500">Loading PRs...</div>
            </div>
          ) : (
            <div className="space-y-3">
              {(prs || []).map((p: any) => (
                <div key={p.number} className="bg-white rounded-lg border border-gray-200 p-4">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="font-medium text-gray-900">#{p.number}</span>
                        <span className={`px-2 py-1 text-xs rounded-full ${getStatusColor(p.status)}`}>
                          {p.status}
                        </span>
                      </div>
                      <div className="font-medium text-gray-900 mb-1">{p.title}</div>
                      <div className="flex items-center gap-4 text-sm text-gray-500">
                        <span>Author: {p.author}</span>
                        <span>Branch: {p.head_branch} → {p.base_branch}</span>
                      </div>
                      <div className="text-sm text-gray-500 mt-1">
                        Created: {formatDate(p.created_at)} • Updated: {formatDate(p.updated_at)}
                      </div>
                      {p.jira_tickets && p.jira_tickets.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1">
                          {p.jira_tickets.map((ticket: string, idx: number) => (
                            <span key={idx} className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded-full">
                              {ticket}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}


