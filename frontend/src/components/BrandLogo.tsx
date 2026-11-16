import { useState } from 'react'
import { classes } from '../lib/format'

/**
 * Logo oficial TrIAgem.
 * - Se existir /logo-triagem.png (ou .jpg) em frontend/public, a variante "full" usa a imagem oficial.
 * - Caso contrário, renderiza a versão vetorial fiel: cruz médica com gradiente #1A93D9 → #8B5CF6,
 *   cão à esquerda, gato à direita e wordmark Tr (azul) · IA (violeta, com ✦) · gem (azul).
 */

const IMAGENS = ['/logo-triagem.png', '/logo-triagem.jpg']

export function MarcaTriagem({ className = 'h-9 w-9' }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={className} role="img" aria-label="TrIAgem" fill="none">
      <defs>
        <linearGradient id="triagem-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#1A93D9" />
          <stop offset="1" stopColor="#8B5CF6" />
        </linearGradient>
      </defs>
      <path
        d="M24 4h16a4 4 0 0 1 4 4v14h14a4 4 0 0 1 4 4v12a4 4 0 0 1-4 4H44v14a4 4 0 0 1-4 4H24a4 4 0 0 1-4-4V42H6a4 4 0 0 1-4-4V26a4 4 0 0 1 4-4h14V8a4 4 0 0 1 4-4z"
        fill="#fff"
        stroke="url(#triagem-g)"
        strokeWidth="3.5"
        strokeLinejoin="round"
      />
      <path
        d="M10 31q0-6 7-6 7 0 7 6.5 0 6.5-7 8.5-7-1-7-9z M10.5 28q-4 2-3 7.5 3.5 1 4.500-3z"
        fill="url(#triagem-g)"
      />
      <path d="M40 40V29l2.800 2.800q4.200-1.800 8.400 0L54 29v11q-7 4.500-14 0z" fill="url(#triagem-g)" />
    </svg>
  )
}

function Estrela({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true" fill="currentColor">
      <path d="M12 0c.8 6.200 5.800 11.200 12 12-6.200.8-11.200 5.800-12 12-.8-6.200-5.800-11.200-12-12C6.200 11.200 11.200 6.200 12 0z" />
    </svg>
  )
}

export function Wordmark({ className = 'text-xl' }: { className?: string }) {
  return (
    <span className={classes('inline-flex items-baseline font-extrabold tracking-tight leading-none', className)}>
      <span className="text-brand">Tr</span>
      <span className="relative text-ai">
        I
        <Estrela className="absolute -top-[0.45em] left-1/2 h-[0.5em] w-[0.5em] -translate-x-1/2" />
      </span>
      <span className="relative text-ai">
        A
        <Estrela className="absolute -top-[0.45em] left-1/2 h-[0.5em] w-[0.5em] -translate-x-1/2" />
      </span>
      <span className="text-brand">gem</span>
    </span>
  )
}

interface BrandLogoProps {
  variant?: 'full' | 'mark' | 'wordmark'
  /** Tamanho do texto do wordmark (classe Tailwind). */
  textSize?: string
  markSize?: string
  selo?: boolean
  className?: string
}

export function BrandLogo({
  variant = 'full',
  textSize = 'text-xl',
  markSize = 'h-9 w-9',
  selo = false,
  className,
}: BrandLogoProps) {
  const [idxImagem, setIdxImagem] = useState(0)
  const usaImagem = variant === 'full' && idxImagem < IMAGENS.length

  if (usaImagem) {
    return (
      <img
        src={IMAGENS[idxImagem]}
        alt="TrIAgem — Triagem Inteligente"
        className={classes('h-10 w-auto object-contain', className)}
        onError={() => setIdxImagem((i) => i + 1)}
      />
    )
  }

  if (variant === 'mark') return <MarcaTriagem className={classes(markSize, className)} />
  if (variant === 'wordmark') return <Wordmark className={textSize} />

  return (
    <span className={classes('inline-flex items-center gap-2.5', className)}>
      <MarcaTriagem className={markSize} />
      <span className="flex flex-col">
        <Wordmark className={textSize} />
        {selo && (
          <span className="mt-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-soft">
            Triagem Inteligente Oficial
          </span>
        )}
      </span>
    </span>
  )
}
