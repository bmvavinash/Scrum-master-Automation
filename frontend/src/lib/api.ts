import { api } from './http'

// Velocity
export const VelocityAPI = {
  getDashboard: (teamId?: string, days: number = 30) =>
    api.get('/velocity/dashboard', { params: { team_id: teamId, days } }).then(r => r.data).catch(() => ({})),
  getInsights: (teamId?: string, sprintId?: string, limit: number = 20) =>
    api.get('/velocity/insights', { params: { team_id: teamId, sprint_id: sprintId, limit } }).then(r => r.data).catch(() => []),
}

// Meetings
export const MeetingsAPI = {
  list: (params?: { meeting_type?: string; status?: string; limit?: number }) =>
    api.get('/meetings/', { params }).then(r => {
      const data = r.data as any
      return Array.isArray(data) ? data : []
    }).catch(() => []),
  create: (meeting: any) => api.post('/meetings/', meeting).then(r => r.data).catch(() => null),
  get: (id: string) => api.get(`/meetings/${id}`).then(r => r.data).catch(() => null),
  addUpdate: (id: string, update: any) => api.post(`/meetings/${id}/updates`, update).then(r => r.data).catch(() => null),
  summarize: (id: string) => api.post(`/meetings/${id}/summarize`, null).then(r => r.data).catch(() => null),
  actionItems: (id: string) => api.get(`/meetings/${id}/action-items`).then(r => {
    const data = r.data as any
    return Array.isArray(data) ? data : []
  }).catch(() => []),
}

// Jira
export const JiraAPI = {
  listTickets: (params?: { project_key?: string; assignee?: string; status?: string; limit?: number }) =>
    api.get('/jira/tickets', { params }).then(r => {
      const data = r.data as any
      if (Array.isArray(data)) return data
      if (data && Array.isArray(data.items)) return data.items
      return []
    }),
  getTicket: (key: string) => api.get(`/jira/tickets/${key}`).then(r => r.data).catch(() => null),
  // Backend expects query/body params, but implemented as function args in FastAPI signature.
  // To be safe across CORS and body parsing, send via params.
  createTicket: (payload: { title: string; description?: string; assignee?: string; project_key?: string; labels?: string[]; story_points?: number; priority?: string; ticket_type?: string }) =>
    api.post('/jira/tickets', null, {
      params: {
        title: payload.title,
        description: payload.description ?? '',
        assignee: payload.assignee,
        project_key: payload.project_key ?? 'SCRUM',
        labels: payload.labels,
        story_points: payload.story_points,
        priority: payload.priority,
        ticket_type: payload.ticket_type,
      }
    }).then(r => r.data).catch(() => null),
  updateStatus: (key: string, new_status: string) => api.put(`/jira/tickets/${key}/status`, null, { params: { new_status } }).then(r => r.data).catch(() => null),
  addComment: (key: string, comment: string) => api.post(`/jira/tickets/${key}/comments`, null, { params: { comment } }).then(r => r.data).catch(() => null),
  createSubtask: (key: string, payload: { title: string; description?: string; assignee?: string }) =>
    api.post(`/jira/tickets/${key}/subtasks`, payload).then(r => r.data).catch(() => null),
  projects: () => api.get('/jira/projects').then(r => {
    const data = r.data as any
    return Array.isArray(data) ? data : []
  }).catch(() => []),
}

// Git
export const GitAPI = {
  dbCommits: (params?: { repository?: string; author?: string; limit?: number }) =>
    api.get('/git/commits', { params }).then(r => {
      const data = r.data as any
      if (Array.isArray(data)) return data
      if (data && Array.isArray(data.items)) return data.items
      return []
    }).catch(() => []),
  dbPullRequests: (params?: { repository?: string; author?: string; status?: string; limit?: number }) =>
    api.get('/git/pull-requests', { params }).then(r => {
      const data = r.data as any
      if (Array.isArray(data)) return data
      if (data && Array.isArray(data.items)) return data.items
      return []
    }).catch(() => []),
}

// Chats / Bot
export const ChatsAPI = {
  help: () => api.get('/chats/bot/help').then(r => r.data).catch(() => null),
  messages: (params?: { channel_id?: string; thread_id?: string; limit?: number }) =>
    api.get('/chats/messages', { params }).then(r => {
      const data = r.data as any
      return Array.isArray(data) ? data : []
    }).catch(() => []),
  sendMessage: (message: any) => api.post('/chats/messages', message).then(r => r.data).catch(() => null),
  processBot: (payload: { message: string; sender_id: string; sender_name: string; channel_id: string; thread_id?: string }) =>
    api.post('/chats/bot/process', null, { params: payload }).then(r => r.data).catch(() => null),
}



