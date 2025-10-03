import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { JiraAPI } from '../lib/api'
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import SectionHeader from '../components/SectionHeader'

export default function Jira() {
  const qc = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  
  // Applied filters (used for API calls)
  const [appliedFilters, setAppliedFilters] = useState({
    project_key: searchParams.get('project_key') || '',
    assignee: searchParams.get('assignee') || '',
    status: searchParams.get('status') || '',
    limit: Number(searchParams.get('limit') || 25)
  })
  
  // Form filters (temporary state before submit)
  const [filterProject, setFilterProject] = useState<string>(appliedFilters.project_key)
  const [filterAssignee, setFilterAssignee] = useState<string>(appliedFilters.assignee)
  const [filterStatus, setFilterStatus] = useState<string>(appliedFilters.status)

  // Apply filters function
  const applyFilters = () => {
    const newFilters = {
      project_key: filterProject,
      assignee: filterAssignee,
      status: filterStatus,
      limit: appliedFilters.limit
    }
    setAppliedFilters(newFilters)
    
    // Update URL
    const params: Record<string, string> = {}
    if (newFilters.project_key) params.project_key = newFilters.project_key
    if (newFilters.assignee) params.assignee = newFilters.assignee
    if (newFilters.status) params.status = newFilters.status
    if (newFilters.limit && newFilters.limit !== 25) params.limit = String(newFilters.limit)
    setSearchParams(params, { replace: true })
  }

  const ticketParams = {
    project_key: appliedFilters.project_key || undefined,
    assignee: appliedFilters.assignee || undefined,
    status: appliedFilters.status || undefined,
    limit: appliedFilters.limit,
  }

  const { data: tickets, isLoading } = useQuery({ queryKey: ['jira','tickets', ticketParams], queryFn: () => JiraAPI.listTickets(ticketParams) })
  const [title, setTitle] = useState('New Task')
  const [description, setDescription] = useState('')
  const [projectKey, setProjectKey] = useState('SCRUM')
  const [priority, setPriority] = useState('Medium')
  const [ticketType, setTicketType] = useState('Task')
  const [selectedTicket, setSelectedTicket] = useState<any>(null)

  const create = useMutation({
    mutationFn: () => JiraAPI.createTicket({ title, description, project_key: projectKey, priority, ticket_type: ticketType }),
    onSuccess: (newTicket: any) => {
      // Ensure lists refresh across any active filter sets
      qc.invalidateQueries({ queryKey: ['jira','tickets'] })
      setSelectedTicket(newTicket)
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
      <SectionHeader
        title="Jira Tickets"
        subtitle="Browse and create issues quickly"
        actions={(
          <div className="flex items-center gap-2 sm:gap-3 flex-wrap">
            <input 
              className="input max-w-xs" 
              value={title} 
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Ticket title"
            />
            <input 
              className="input max-w-[10rem]" 
              value={projectKey}
              onChange={(e) => setProjectKey(e.target.value)}
              placeholder="Project key"
            />
            <select className="input max-w-[10rem]" value={ticketType} onChange={e => setTicketType(e.target.value)}>
              <option>Task</option>
              <option>Bug</option>
              <option>Story</option>
              <option>Epic</option>
              <option>Sub-task</option>
            </select>
            <select className="input max-w-[10rem]" value={priority} onChange={e => setPriority(e.target.value)}>
              <option>Highest</option>
              <option>High</option>
              <option>Medium</option>
              <option>Low</option>
              <option>Lowest</option>
            </select>
            <button 
              className="btn-primary" 
              onClick={() => create.mutate()}
              disabled={!title.trim()}
            >
              Create Ticket
            </button>
          </div>
        )}
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Tickets List */}
        <div className="space-y-4">
          <h2 className="text-xl sm:text-2xl font-semibold text-gray-800">Recent Tickets</h2>
          {/* Filters */}
          <div className="card p-4">
            <div className="flex items-center gap-2 sm:gap-3 flex-wrap">
              <input
                className="input max-w-[12rem]"
                value={filterProject}
                onChange={(e) => setFilterProject(e.target.value)}
                placeholder="Filter by project key"
              />
              <input
                className="input max-w-[12rem]"
                value={filterAssignee}
                onChange={(e) => setFilterAssignee(e.target.value)}
                placeholder="Filter by assignee"
              />
              <select
                className="input max-w-[12rem]"
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
              >
                <option value="">All Statuses</option>
                <option>To Do</option>
                <option>In Progress</option>
                <option>In Review</option>
                <option>Done</option>
              </select>
              <button
                className="btn-primary"
                onClick={applyFilters}
              >
                Apply Filters
              </button>
              <button
                className="btn"
                onClick={() => {
                  setFilterProject('')
                  setFilterAssignee('')
                  setFilterStatus('')
                  setAppliedFilters({
                    project_key: '',
                    assignee: '',
                    status: '',
                    limit: 25
                  })
                  setSearchParams({}, { replace: true })
                }}
              >
                Clear Filters
              </button>
            </div>
          </div>
          <div className="space-y-3">
            {(tickets || []).map((t: any) => (
              <div 
                key={t.jira_key} 
                className="card p-4 hover:shadow-md transition-shadow cursor-pointer"
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
                    <h3 className="font-semibold text-gray-900 mb-1 line-clamp-2">{t.title}</h3>
                    <div className="flex flex-wrap items-center gap-2 sm:gap-4 text-sm text-gray-500">
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
          <h2 className="text-xl sm:text-2xl font-semibold text-gray-800">Ticket Details</h2>
          {selectedTicket ? (
            <div className="card p-6">
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
                
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
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
                        <span key={idx} className="px-2 py-1 bg-brand-50 text-brand-700 text-xs rounded-full">
                          {label}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="card p-6 text-center">
              <div className="text-gray-500">Select a ticket to view details</div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}


