import { useState, useEffect, useRef } from 'react';
import { listen } from '@tauri-apps/api/event';
import { invoke } from '@tauri-apps/api/core';

interface RawMessage {
  id: number;
  ts: string;
  parsed: unknown;
  kind: 'mqtt' | 'ssdp' | 'tx';
}

let seq = 0;

export default function DebugPage({ onMenuOpen }: { onMenuOpen: () => void }) {
  const [messages, setMessages] = useState<RawMessage[]>([]);
  const [paused, setPaused] = useState(false);
  const [showSsdp, setShowSsdp] = useState(false);
  const pausedRef = useRef(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  pausedRef.current = paused;

  useEffect(() => {
    const unsub = listen<string>('mqtt-raw', (e) => {
      if (pausedRef.current) return;
      let parsed: unknown;
      try { parsed = JSON.parse(e.payload); } catch { parsed = e.payload; }
      setMessages((prev) => [...prev.slice(-199), { id: ++seq, ts: new Date().toLocaleTimeString(), parsed, kind: 'mqtt' as const }]);
    });
    const unsubSsdp = listen<string>('ssdp-debug', (e) => {
      if (pausedRef.current) return;
      setMessages((prev) => [...prev.slice(-199), { id: ++seq, ts: new Date().toLocaleTimeString(), parsed: e.payload, kind: 'ssdp' as const }]);
    });
    return () => { unsub.then((f) => f()); unsubSsdp.then((f) => f()); };
  }, []);

  useEffect(() => {
    if (!paused) bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, paused]);

  const sendRequest = (payload: unknown) => {
    setMessages((prev) => [...prev.slice(-199), {
      id: ++seq,
      ts: new Date().toLocaleTimeString(),
      parsed: payload,
      kind: 'tx' as const,
    }]);
    invoke('debug_send_request', { payload: JSON.stringify(payload) }).catch((err) => {
      setMessages((prev) => [...prev.slice(-199), {
        id: ++seq,
        ts: new Date().toLocaleTimeString(),
        parsed: `SEND ERROR: ${String(err)}`,
        kind: 'tx' as const,
      }]);
    });
  };

  const visibleMessages = showSsdp ? messages : messages.filter((m) => m.kind !== 'ssdp');

  return (
    <div className='min-h-screen bg-zinc-950 text-white flex flex-col'>
      <div
        className='sticky top-0 z-10 px-3 pb-3 bg-zinc-900 border-b border-zinc-800 shrink-0'
        style={{ paddingTop: 'calc(env(safe-area-inset-top, 0px) + 0.75rem)' }}>
        <div className='flex items-center justify-between mb-2'>
          <button onClick={onMenuOpen} className='text-zinc-400 hover:text-white transition-colors' aria-label='Menu'>
            <svg className='w-6 h-6' fill='none' viewBox='0 0 24 24' stroke='currentColor' strokeWidth={2}>
              <path strokeLinecap='round' strokeLinejoin='round' d='M4 6h16M4 12h16M4 18h16' />
            </svg>
          </button>
          <h1 className='font-semibold text-base'>MQTT Debug — X2D.2</h1>
          <div className='w-6' />
        </div>

        <div className='flex flex-wrap items-center justify-center gap-1.5'>
          <button
            onClick={() => sendRequest({ pushing: { sequence_id: '20001', command: 'pushall', version: 1, push_target: 1 } })}
            className='text-xs font-mono px-2 py-1.5 rounded bg-teal-800 text-teal-100 hover:bg-teal-700 transition-colors'>
            X2D Pushall
          </button>
          <button
            onClick={() => sendRequest({ pushing: { sequence_id: '20002', command: 'start' } })}
            className='text-xs font-mono px-2 py-1.5 rounded bg-teal-800 text-teal-100 hover:bg-teal-700 transition-colors'>
            Start
          </button>
          <button
            onClick={() => sendRequest({ info: { sequence_id: '20003', command: 'get_version' } })}
            className='text-xs font-mono px-2 py-1.5 rounded bg-teal-800 text-teal-100 hover:bg-teal-700 transition-colors'>
            Version
          </button>
          <button
            onClick={() => setPaused((p) => !p)}
            className={`text-xs font-mono px-2 py-1.5 rounded transition-colors ${
              paused ? 'bg-yellow-700 text-yellow-100' : 'bg-zinc-700 text-zinc-200 hover:bg-zinc-600'
            }`}>
            {paused ? 'Resume' : 'Pause'}
          </button>
          <button
            onClick={() => setMessages([])}
            className='text-xs font-mono px-2 py-1.5 rounded bg-zinc-700 text-zinc-200 hover:bg-zinc-600 transition-colors'>
            Clear
          </button>
          <button
            onClick={() => setShowSsdp((v) => !v)}
            className={`text-xs font-mono px-2 py-1.5 rounded transition-colors ${
              showSsdp ? 'bg-blue-800 text-blue-100' : 'bg-zinc-800 text-zinc-400'
            }`}>
            SSDP {showSsdp ? 'ON' : 'OFF'}
          </button>
        </div>
      </div>

      <div className='flex-1 overflow-y-auto p-3 flex flex-col gap-2 font-mono text-xs'>
        {visibleMessages.length === 0 && (
          <p className='text-zinc-600 text-center py-12'>Waiting for MQTT messages…</p>
        )}
        {visibleMessages.map((msg) => {
          const isSsdp = msg.kind === 'ssdp';
          const isTx = msg.kind === 'tx';
          return (
            <div key={msg.id} className={`border rounded-lg overflow-hidden ${
              isSsdp ? 'bg-blue-950 border-blue-800' : isTx ? 'bg-amber-950 border-amber-800' : 'bg-zinc-900 border-zinc-800'
            }`}>
              <div className={`flex items-center gap-2 px-3 py-1.5 border-b ${
                isSsdp ? 'bg-blue-900 border-blue-800' : isTx ? 'bg-amber-900 border-amber-800' : 'bg-zinc-800 border-zinc-700'
              }`}>
                <span className={isSsdp ? 'text-blue-300 font-bold' : isTx ? 'text-amber-300 font-bold' : 'text-zinc-500'}>#{msg.id}</span>
                <span className='text-zinc-400'>{msg.ts}</span>
                <span className={`ml-auto text-xs font-bold ${isSsdp ? 'text-blue-300' : isTx ? 'text-amber-300' : 'text-green-400'}`}>
                  {isSsdp ? 'SSDP' : isTx ? `TX ${topLevelKey(msg.parsed)}` : topLevelKey(msg.parsed)}
                </span>
              </div>
              <pre className={`p-3 overflow-x-auto whitespace-pre-wrap break-all leading-relaxed ${
                isSsdp ? 'text-blue-300' : isTx ? 'text-amber-200' : 'text-green-400'
              }`}>
                {typeof msg.parsed === 'string' ? msg.parsed : JSON.stringify(msg.parsed, null, 2)}
              </pre>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

function topLevelKey(parsed: unknown): string {
  if (parsed && typeof parsed === 'object') {
    return Object.keys(parsed as object).join(', ');
  }
  return '';
}
