import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { MeetingsAPI } from '../lib/api'
import { useState } from 'react'

export default function Meetings() {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({ queryKey: ['meetings'], queryFn: () => MeetingsAPI.list({ limit: 50 }) })
  const [title, setTitle] = useState('Daily Standup')
  const [selectedMeeting, setSelectedMeeting] = useState<any>(null)

  const create = useMutation({
    mutationFn: () => MeetingsAPI.create({ name: title, meeting_type: 'standup', status: 'scheduled', participant_updates: [] }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['meetings'] }),
  })

  if (isLoading) return <div className="flex items-center justify-center h-64"><div className="text-gray-500">Loading meetings...</div></div>

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Meetings</h1>
        <div className="flex items-center gap-3">
          <input 
            className="border border-gray-300 rounded-lg px-4 py-2 focus:ring-2 focus:ring-blue-500 focus:border-transparent" 
            value={title} 
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Meeting name"
          />
          <button 
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors" 
            onClick={() => create.mutate()}
            disabled={!title.trim()}
          >
            Create Meeting
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Meetings List */}
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-gray-800">Recent Meetings</h2>
          <div className="space-y-3">
            {(data || []).map((m: any) => (
              <div 
                key={m.id} 
                className="bg-white rounded-lg border border-gray-200 p-4 hover:shadow-md transition-shadow cursor-pointer"
                onClick={() => setSelectedMeeting(m)}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-medium text-gray-900">{m.title}</h3>
                    <div className="flex items-center gap-2 mt-1">
                      <span className={`px-2 py-1 text-xs rounded-full ${
                        m.status === 'completed' ? 'bg-green-100 text-green-800' :
                        m.status === 'active' ? 'bg-blue-100 text-blue-800' :
                        'bg-gray-100 text-gray-800'
                      }`}>
                        {m.status}
                      </span>
                      <span className="text-sm text-gray-500 capitalize">{m.meeting_type}</span>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm text-gray-500">
                      {m.participant_updates?.length || 0} updates
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Meeting Details */}
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-gray-800">Meeting Details</h2>
          {selectedMeeting ? (
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h3 className="text-xl font-semibold text-gray-900 mb-4">{selectedMeeting.title}</h3>
              
              <div className="space-y-4">
                <div>
                  <h4 className="font-medium text-gray-700 mb-2">Participant Updates</h4>
                  {selectedMeeting.participant_updates?.length > 0 ? (
                    <div className="space-y-3">
                      {selectedMeeting.participant_updates.map((update: any, idx: number) => (
                        <div key={idx} className="bg-gray-50 rounded-lg p-4">
                          <div className="font-medium text-gray-900">{update.participant_name}</div>
                          <div className="mt-2 space-y-2 text-sm">
                            <div><span className="font-medium">Yesterday:</span> {update.yesterday_work}</div>
                            <div><span className="font-medium">Today:</span> {update.today_plan}</div>
                            {update.blockers && update.blockers.length > 0 && (
                              <div><span className="font-medium text-red-600">Blockers:</span> {update.blockers.join(', ')}</div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-gray-500 text-sm">No participant updates yet</div>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-white rounded-lg border border-gray-200 p-6 text-center">
              <div className="text-gray-500">Select a meeting to view details</div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}


