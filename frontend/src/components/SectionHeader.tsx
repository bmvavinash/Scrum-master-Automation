import React from 'react'

type Props = {
  title: string
  subtitle?: string
  actions?: React.ReactNode
}

export default function SectionHeader({ title, subtitle, actions }: Props) {
  return (
    <div className="mb-6 sm:mb-8">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
        <div>
          <h1 className="font-extrabold tracking-tight text-2xl sm:text-3xl md:text-4xl text-gray-900">
            {title}
          </h1>
          {subtitle && (
            <p className="mt-1 text-sm sm:text-base text-gray-600">{subtitle}</p>
          )}
        </div>
        {actions && (
          <div className="flex items-center gap-2 sm:gap-3">{actions}</div>
        )}
      </div>
    </div>
  )
}



