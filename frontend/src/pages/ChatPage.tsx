import { useState, useRef, useEffect, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import { Send, Bot, User, Sparkles, RotateCcw } from 'lucide-react'
import { WS_BASE } from '../api'

interface Message { role: 'user' | 'assistant'; content: string }

const SUGGESTED = [
  { emoji: '🎓', text: 'What are the PhD requirements for Computer Science at NUS?' },
  { emoji: '📚', text: 'Tell me about the NUS Master of Computing program' },
  { emoji: '📅', text: 'Sync my Canvas assignments and download my calendar' },
  { emoji: '💼', text: 'Help me find and apply for software engineer internships on LinkedIn' },
  { emoji: '📄', text: 'How do I upload my syllabus to extract exam dates?' },
  { emoji: '📧', text: 'Send my schedule to my email with reminders' },
]

function TypingDots() {
  return (
    <div className="flex gap-1 items-center py-1">
      {[0,1,2].map(i => (
        <div key={i} className="w-1.5 h-1.5 rounded-full bg-gray-300 animate-bounce" style={{ animationDelay: `${i*0.15}s` }} />
      ))}
    </div>
  )
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'assistant', content: "Hello! I'm your **NUS Campus Assistant**, powered by OpenClaw agents and WaveSpeed AI.\n\nI have knowledge about NUS programs, modules, admissions, campus life, and more. How can I help you today?" },
  ])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = useCallback((question: string) => {
    if (!question.trim() || isStreaming) return

    setMessages(prev => [...prev, { role: 'user', content: question }, { role: 'assistant', content: '' }])
    setInput('')
    setIsStreaming(true)

    const ws = new WebSocket(`${WS_BASE}/api/knowledge/ws/chat`)
    wsRef.current = ws

    ws.onopen = () => {
      ws.send(JSON.stringify({ question, chat_history: messages.slice(-8) }))
    }
    ws.onmessage = (e) => {
      const data = JSON.parse(e.data)
      if (data.type === 'token') {
        setMessages(prev => {
          const updated = [...prev]
          updated[updated.length - 1] = { ...updated[updated.length - 1], content: updated[updated.length - 1].content + data.content }
          return updated
        })
      } else if (data.type === 'done') {
        setIsStreaming(false)
        ws.close()
        inputRef.current?.focus()
      } else if (data.type === 'error') {
        setMessages(prev => { const u = [...prev]; u[u.length-1].content = `Sorry, something went wrong: ${data.content}`; return u })
        setIsStreaming(false)
        ws.close()
      }
    }
    ws.onerror = () => {
      setMessages(prev => { const u = [...prev]; u[u.length-1].content = 'Cannot connect to backend. Please make sure the server is running on port 8000.'; return u })
      setIsStreaming(false)
    }
  }, [isStreaming, messages])

  const reset = () => {
    wsRef.current?.close()
    setMessages([{ role: 'assistant', content: "Hello! I'm your **NUS Campus Assistant**. How can I help you today?" }])
    setIsStreaming(false)
    setInput('')
  }

  const isLastStreaming = isStreaming && messages[messages.length - 1]?.role === 'assistant'

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="bg-white border-b border-gray-100 px-5 py-3 flex items-center justify-between shrink-0">
        <div>
          <h1 className="font-semibold text-gray-800 text-sm">NUS Knowledge Q&A</h1>
          <p className="text-xs text-gray-400">ChromaDB RAG · WaveSpeed AI · OpenClaw knowledge_agent</p>
        </div>
        <button onClick={reset} className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors" title="New chat">
          <RotateCcw size={15} />
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 scrollable px-4 py-5 space-y-5">
        {messages.map((msg, i) => (
          <div key={i} className={`flex gap-3 animate-slide-up ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {msg.role === 'assistant' && (
              <div className="w-7 h-7 rounded-full bg-nus-blue flex items-center justify-center shrink-0 mt-0.5 shadow-sm">
                <Bot size={14} className="text-white" />
              </div>
            )}
            <div className={msg.role === 'user' ? 'bubble-user' : 'bubble-ai'}>
              {msg.role === 'assistant'
                ? msg.content
                  ? <div className={`prose-chat ${isLastStreaming && i === messages.length - 1 ? 'typing-cursor' : ''}`}>
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                  : <TypingDots />
                : <span className="text-sm">{msg.content}</span>
              }
            </div>
            {msg.role === 'user' && (
              <div className="w-7 h-7 rounded-full bg-gray-200 flex items-center justify-center shrink-0 mt-0.5">
                <User size={14} className="text-gray-500" />
              </div>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Suggestions */}
      {messages.length <= 1 && (
        <div className="px-4 pb-3">
          <div className="flex items-center gap-1.5 mb-2">
            <Sparkles size={12} className="text-nus-orange" />
            <span className="text-xs text-gray-400 font-medium">Suggested questions</span>
          </div>
          <div className="grid grid-cols-2 gap-2 max-h-40 overflow-y-auto">
            {SUGGESTED.map((s, i) => (
              <button key={i} onClick={() => sendMessage(s.text)}
                className="text-left text-xs bg-white border border-gray-200 rounded-xl px-3 py-2.5 text-gray-600 hover:border-nus-blue hover:text-nus-blue hover:bg-blue-50 transition-all leading-relaxed">
                <span className="mr-1.5">{s.emoji}</span>{s.text}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <div className="bg-white border-t border-gray-100 px-4 py-3 shrink-0">
        <form onSubmit={e => { e.preventDefault(); sendMessage(input) }} className="flex gap-2">
          <input ref={inputRef} type="text" value={input} onChange={e => setInput(e.target.value)}
            placeholder="Ask anything about NUS..."
            disabled={isStreaming}
            className="flex-1 input text-sm" />
          <button type="submit" disabled={isStreaming || !input.trim()} className="btn-primary px-3">
            <Send size={15} />
          </button>
        </form>
        <p className="text-xs text-gray-300 text-center mt-1.5">Powered by WaveSpeed AI · May make mistakes</p>
      </div>
    </div>
  )
}
