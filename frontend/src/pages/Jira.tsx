import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { JiraAPI } from '../lib/api'
import { useState } from 'react'

export default function Jira() {
  const qc = useQueryClient()
  const { data: tickets, isLoading } = useQuery({ queryKey: ['jira','tickets'], queryFn: () => JiraAPI.listTickets({ limit: 25 }) })
  const [title, setTitle] = useState('New Task')
  const [description, setDescription] = useState('')
  const [selectedTicket, setSelectedTicket] = useState<any>(null)

  const create = useMutation({
    mutationFn: () => JiraAPI.createTicket({ title, description }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['jira','tickets'] })
      setTitle('New Task')
      setDescription('')
    },
  })

  const getStatusColor = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'done': return 'bg-green-100 text-green-800'
      case 'in progress': return 'bg-blue-100 text-blue-800'
      case 'to do': return 'bg-gray-100 text-gray-800'
      case 'in review': return 'bg-yellow-100 text-yellow-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  const getPriorityColor = (priority: string) => {
    switch (priority?.toLowerCase()) {
      case 'critical': return 'bg-red-100 text-red-800'
      case 'high': return 'bg-orange-100 text-orange-800'
      case 'medium': return 'bg-yellow-100 text-yellow-800'
      case 'low': return 'bg-green-100 text-green-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  if (isLoading) return <div className="flex items-center justify-center h-64"><div className="text-gray-500">Loading tickets...</div></div>

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Jira Tickets</h1>
        <div className="flex items-center gap-3">
          <input 
            className="border border-gray-300 rounded-lg px-4 py-2 focus:ring-2 focus:ring-blue-500 focus:border-transparent" 
            value={title} 
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Ticket title"
          />
          <button 
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors" 
            onClick={() => create.mutate()}
            disabled={!title.trim()}
          >
            Create Ticket
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Tickets List */}
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-gray-800">Recent Tickets</h2>
          <div className="space-y-3">
            {(tickets || []).map((t: any) => (
              <div 
                key={t.jira_key} 
                className="bg-white rounded-lg border border-gray-200 p-4 hover:shadow-md transition-shadow cursor-pointer"
                onClick={() => setSelectedTicket(t)}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="font-medium text-gray-900">{t.jira_key}</span>
                      <span className={`px-2 py-1 text-xs rounded-full ${getStatusColor(t.status)}`}>
                        {t.status}
                      </span>
                      <span className={`px-2 py-1 text-xs rounded-full ${getPriorityColor(t.priority)}`}>
                        {t.priority}
                      </span>
                    </div>
                    <h3 className="font-medium text-gray-900 mb-1">{t.title}</h3>
                    <div className="flex items-center gap-4 text-sm text-gray-500">
                      <span>Type: {t.ticket_type}</span>
                      {t.story_points && <span>Points: {t.story_points}</span>}
                      <span>Assignee: {t.assignee}</span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Ticket Details */}
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-gray-800">Ticket Details</h2>
          {selectedTicket ? (
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <div className="flex items-center gap-2 mb-4">
                <h3 className="text-xl font-semibold text-gray-900">{selectedTicket.jira_key}</h3>
                <span className={`px-2 py-1 text-xs rounded-full ${getStatusColor(selectedTicket.status)}`}>
                  {selectedTicket.status}
                </span>
                <span className={`px-2 py-1 text-xs rounded-full ${getPriorityColor(selectedTicket.priority)}`}>
                  {selectedTicket.priority}
                </span>
              </div>
              
              <h4 className="text-lg font-medium text-gray-900 mb-3">{selectedTicket.title}</h4>
              
              <div className="space-y-4">
                <div>
                  <h5 className="font-medium text-gray-700 mb-2">Description</h5>
                  <p className="text-gray-600">{selectedTicket.description || 'No description provided'}</p>
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <h5 className="font-medium text-gray-700 mb-1">Type</h5>
                    <p className="text-gray-600">{selectedTicket.ticket_type}</p>
                  </div>
                  <div>
                    <h5 className="font-medium text-gray-700 mb-1">Story Points</h5>
                    <p className="text-gray-600">{selectedTicket.story_points || 'Not estimated'}</p>
                  </div>
                  <div>
                    <h5 className="font-medium text-gray-700 mb-1">Assignee</h5>
                    <p className="text-gray-600">{selectedTicket.assignee || 'Unassigned'}</p>
                  </div>
                  <div>
                    <h5 className="font-medium text-gray-700 mb-1">Reporter</h5>
                    <p className="text-gray-600">{selectedTicket.reporter || 'Unknown'}</p>
                  </div>
                </div>
                
                {selectedTicket.labels && selectedTicket.labels.length > 0 && (
                  <div>
                    <h5 className="font-medium text-gray-700 mb-2">Labels</h5>
                    <div className="flex flex-wrap gap-2">
                      {selectedTicket.labels.map((label: string, idx: number) => (
                        <span key={idx} className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded-full">
                          {label}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="bg-white rounded-lg border border-gray-200 p-6 text-center">
              <div className="text-gray-500">Select a ticket to view details</div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}


