import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChatsAPI } from '../lib/api'
import { useEffect, useRef, useState } from 'react'
import SectionHeader from '../components/SectionHeader'

export default function Chat() {
  const qc = useQueryClient()
  const { data: messages } = useQuery({ queryKey: ['chat','messages'], queryFn: () => ChatsAPI.messages({ limit: 30 }) })
  const [text, setText] = useState('')
  const [isTyping, setIsTyping] = useState(false)
  const scrollRef = useRef<HTMLDivElement | null>(null)

  const send = useMutation({
    mutationFn: () => ChatsAPI.processBot({ message: text, sender_id: 'user1', sender_name: 'User', channel_id: 'general' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['chat','messages'] })
      setText('')
      setIsTyping(false)
    },
    onError: () => {
      setIsTyping(false)
    }
  })

  const handleSend = () => {
    if (!text.trim()) return
    setIsTyping(true)
    send.mutate()
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const formatTime = (dateString: string) => {
    if (!dateString) return ''
    return new Date(dateString).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  // Ensure oldest-to-newest ordering
  const orderedMessages = (messages || [])
    .slice()
    .sort((a: any, b: any) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [orderedMessages.length, isTyping])

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Bot Chat"
        subtitle="Try commands like /help, /create-task, /get-velocity"
      />

      <div className="card h-[32rem] sm:h-[34rem] flex flex-col">
        {/* Chat Header */}
        <div className="border-b border-gray-200 p-4">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-brand-500 rounded-full"></div>
            <span className="font-medium text-gray-900">Scrum Bot</span>
            <span className="text-sm text-gray-500">Online</span>
          </div>
        </div>

        {/* Messages */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
          {orderedMessages.map((m: any, idx: number) => (
            <div key={idx} className={`flex ${m.sender_id === 'user1' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                m.sender_id === 'user1' 
                  ? 'bg-brand-600 text-white' 
                  : 'bg-gray-100 text-gray-900'
              }`}>
                <div className="text-sm">{m.content}</div>
                <div className={`text-xs mt-1 ${
                  m.sender_id === 'user1' ? 'text-brand-100' : 'text-gray-500'
                }`}>
                  {m.sender_name} • {formatTime(m.created_at)}
                </div>
              </div>
            </div>
          ))}
          
          {isTyping && (
            <div className="flex justify-start">
              <div className="bg-gray-100 text-gray-900 px-4 py-2 rounded-lg">
                <div className="flex items-center gap-1">
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Input */}
        <div className="border-t border-gray-200 p-3 sm:p-4 sticky bottom-0 bg-white rounded-b-xl">
          <div className="flex items-center gap-3">
            <input 
              className="flex-1 input" 
              value={text} 
              onChange={(e) => setText(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Type a message or command (e.g., /help)"
              disabled={isTyping}
            />
            <button 
              className="btn-primary" 
              onClick={handleSend} 
              disabled={!text.trim() || isTyping}
            >
              Send
            </button>
          </div>
        </div>
      </div>

      {/* Quick Commands */}
      <div className="bg-gray-50 rounded-xl p-4">
        <h3 className="font-medium text-gray-900 mb-2">Quick Commands</h3>
        <div className="flex flex-wrap gap-2">
          {['/help', '/create-task', '/get-velocity', '/get-status', '/create-blocker'].map((cmd) => (
            <button
              key={cmd}
              className="px-3 py-1 bg-white border border-gray-200 rounded-lg text-sm hover:bg-brand-50 hover:border-brand-200 hover:text-brand-700 transition-colors"
              onClick={() => setText(cmd)}
            >
              {cmd}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}


