import type { PrinterConfig } from '../vite-env';
import { serialToModel } from '../utils/hmsErrors';

export type Page = 'dashboard' | 'files' | 'timelapses' | 'printers' | 'printer-settings' | 'debug';

const NAV = [
  {
    page: 'dashboard' as Page,
    label: 'Dashboard',
    icon: (
      <svg className='w-5 h-5' fill='none' viewBox='0 0 24 24' stroke='currentColor' strokeWidth={1.75}>
        <rect x='3' y='3' width='7' height='7' rx='1' />
        <rect x='14' y='3' width='7' height='7' rx='1' />
        <rect x='3' y='14' width='7' height='7' rx='1' />
        <rect x='14' y='14' width='7' height='7' rx='1' />
      </svg>
    ),
  },
  {
    page: 'files' as Page,
    label: 'File Manager',
    icon: (
      <svg className='w-5 h-5' fill='none' viewBox='0 0 24 24' stroke='currentColor' strokeWidth={1.75}>
        <path strokeLinecap='round' strokeLinejoin='round' d='M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V7z' />
      </svg>
    ),
  },
  {
    page: 'timelapses' as Page,
    label: 'Timelapses',
    icon: (
      <svg className='w-5 h-5' fill='none' viewBox='0 0 24 24' stroke='currentColor' strokeWidth={1.75}>
        <path strokeLinecap='round' strokeLinejoin='round' d='M15 10l4.553-2.069A1 1 0 0121 8.82v6.36a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z' />
      </svg>
    ),
  },
  {
    page: 'printers' as Page,
    label: 'Printers',
    icon: (
      <svg className='w-5 h-5' fill='none' viewBox='0 0 24 24' stroke='currentColor' strokeWidth={1.75}>
        <path strokeLinecap='round' strokeLinejoin='round' d='M5 6a4 4 0 014-4h6a4 4 0 014 4v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6z' />
        <path strokeLinecap='round' strokeLinejoin='round' d='M15 7v6' />
      </svg>
    ),
  },
  {
    page: 'debug' as Page,
    label: 'MQTT Debug',
    icon: (
      <svg className='w-5 h-5' fill='none' viewBox='0 0 24 24' stroke='currentColor' strokeWidth={1.75}>
        <path strokeLinecap='round' strokeLinejoin='round' d='M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z' />
      </svg>
    ),
  },
] as const;

export default function Sidebar({
  open,
  onClose,
  page,
  onNavigate,
  activePrinter,
  deviceName,
}: {
  open: boolean;
  onClose: () => void;
  page: Page;
  onNavigate: (p: Page) => void;
  activePrinter: PrinterConfig | null;
  deviceName?: string;
}) {
  const model = activePrinter ? serialToModel(activePrinter.serial) : null;
  const displayName = activePrinter
    ? activePrinter.nickname || deviceName || (model ? `My ${model}` : activePrinter.ip)
    : '';

  return (
    <>
      <div
        className={`fixed inset-0 bg-black/65 z-40 transition-opacity duration-300 ${
          open ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'
        }`}
        onClick={onClose}
      />

      <div
        className={`fixed top-0 right-0 h-full w-64 bg-[#07111d] border-l border-cyan-400/15 z-50 flex flex-col transform transition-transform duration-300 ease-in-out shadow-[-16px_0_40px_rgba(0,0,0,0.35)] ${
          open ? 'translate-x-0' : 'translate-x-full'
        }`}
        style={{ paddingTop: 'env(safe-area-inset-top, 0px)' }}>
        <div className='flex items-center justify-between px-4 py-3.5 border-b border-cyan-400/15'>
          <div className='flex min-w-0 items-center gap-2.5'>
            <img
              src='/scd-x2d-icon.png'
              alt='SCD X2D'
              className='h-9 w-9 shrink-0 rounded-xl border border-cyan-300/25 shadow-[0_0_14px_rgba(34,211,238,0.16)]'
            />
            <div className='min-w-0 leading-none'>
              <div className='flex items-baseline gap-1.5'>
                <span className='text-sm font-extrabold tracking-[0.12em] text-slate-100'>SCD</span>
                <span className='text-lg font-black tracking-tight text-cyan-300'>X2D</span>
              </div>
              <div className='mt-1 text-[9px] font-semibold uppercase tracking-[0.18em] text-slate-500'>Printer Control</div>
            </div>
          </div>
          <button
            onClick={onClose}
            className='text-slate-500 hover:text-cyan-200 transition-colors w-8 h-8 flex items-center justify-center rounded-lg hover:bg-cyan-400/10'>
            <svg className='w-5 h-5' fill='none' viewBox='0 0 24 24' stroke='currentColor' strokeWidth={2}>
              <path strokeLinecap='round' strokeLinejoin='round' d='M6 18L18 6M6 6l12 12' />
            </svg>
          </button>
        </div>

        {activePrinter && (
          <button
            onClick={() => onNavigate('printers')}
            className='flex items-center gap-3 mx-3 mt-3 px-3 py-2.5 bg-[#0a1725] hover:bg-[#0d1d2e] border border-cyan-400/10 rounded-xl transition-colors text-left'>
            <div className='w-2 h-2 rounded-full bg-cyan-300 shadow-[0_0_9px_rgba(103,232,249,0.75)] shrink-0' />
            <div className='flex flex-col min-w-0 flex-1'>
              <span className='text-slate-100 text-sm font-medium truncate'>{displayName}</span>
              <span className='text-slate-500 text-xs font-mono truncate'>{activePrinter.ip}</span>
            </div>
            <svg className='w-4 h-4 text-slate-500 shrink-0' fill='none' viewBox='0 0 24 24' stroke='currentColor' strokeWidth={2}>
              <path strokeLinecap='round' strokeLinejoin='round' d='M8 9l4-4 4 4m0 6l-4 4-4-4' />
            </svg>
          </button>
        )}

        <nav className='flex flex-col p-3 gap-1 flex-1 mt-1'>
          {NAV.map((item) => (
            <button
              key={item.page}
              onClick={() => onNavigate(item.page)}
              className={`flex items-center gap-3 px-4 py-3 rounded-xl text-left transition-colors ${
                page === item.page ?
                  'bg-cyan-400/15 text-cyan-300 border border-cyan-400/15'
                : 'text-slate-300 border border-transparent hover:bg-cyan-400/8 hover:text-slate-100'
              }`}>
              {item.icon}
              <span className='font-medium text-sm'>{item.label}</span>
            </button>
          ))}
        </nav>
      </div>
    </>
  );
}
