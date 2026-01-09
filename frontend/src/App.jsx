import { useState, useRef } from 'react'
import { Mic, Loader2, Music, CheckCircle2, XCircle } from 'lucide-react'
import './App.css'

function App() {
  const [status, setStatus] = useState('idle') // idle, recording, analyzing, success, error
  const [result, setResult] = useState(null)
  const mediaRecorderRef = useRef(null)

  const startRecording = async () => {
    setStatus('recording')
    setResult(null)

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      
      // Determine the best MIME type (Chrome vs Safari)
      let mimeType = 'audio/webm;codecs=opus'
      if (!MediaRecorder.isTypeSupported(mimeType)) {
        mimeType = 'audio/mp4' // Safari fallback
      }

      const mediaRecorder = new MediaRecorder(stream, { mimeType })
      mediaRecorderRef.current = mediaRecorder
      const audioChunks = []

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) audioChunks.push(event.data)
      }

      mediaRecorder.onstop = async () => {
        setStatus('analyzing')
        const audioBlob = new Blob(audioChunks, { type: mimeType })
        const formData = new FormData()
        formData.append("file", audioBlob, "recording.webm")

        try {
          // REPLACE WITH YOUR RENDER BACKEND URL 
          // Example: https://audioprint-xyz.onrender.com/identify
          const response = await fetch("https://audio-print.onrender.com", {
            method: "POST",
            body: formData
          })
          const data = await response.json()

          if (data.status === 'success') {
            setStatus('success')
            setResult(data)
          } else {
            setStatus('error')
          }
        } catch (error) {
          console.error(error)
          setStatus('error')
        }
        
        stream.getTracks().forEach(track => track.stop())
      }

      mediaRecorder.start()

      // Stop automatically after 10 seconds
      setTimeout(() => {
        if (mediaRecorder.state !== 'inactive') {
          mediaRecorder.stop()
        }
      }, 10000)

    } catch (err) {
      alert("Microphone access denied!")
      setStatus('idle')
    }
  }

  return (
    <div className="container">
      <div className="card">
        <h1>🎵 AudioPrint</h1>
        <p>Shazam-like Audio Recognition</p>

        <div className="status-box">
          {status === 'idle' && <div className="icon-box"><Music size={48} /></div>}
          {status === 'recording' && <div className="icon-box pulse"><Mic size={48} color="red" /></div>}
          {status === 'analyzing' && <div className="icon-box spin"><Loader2 size={48} /></div>}
          {status === 'success' && <div className="icon-box"><CheckCircle2 size={48} color="green" /></div>}
          {status === 'error' && <div className="icon-box"><XCircle size={48} color="orange" /></div>}
        </div>

        <button 
          onClick={startRecording} 
          disabled={status === 'recording' || status === 'analyzing'}
        >
          {status === 'recording' ? 'Listening (10s)...' : '🎙️ Identify Song'}
        </button>

        {status === 'success' && result && (
          <div className="result">
            <h2>{result.song}</h2>
            <div className="stats">
              <p><strong>Confidence:</strong> {result.confidence} matches</p>
              <p><strong>Offset:</strong> {result.offset_seconds}s</p>
            </div>
          </div>
        )}

        {status === 'error' && (
          <p className="error-msg">No match found or server error.</p>
        )}
      </div>
    </div>
  )
}

export default App