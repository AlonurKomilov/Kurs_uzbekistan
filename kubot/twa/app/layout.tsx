import type { Metadata, Viewport } from 'next'
import { ReactNode } from 'react'
import './globals.css'

export const metadata: Metadata = {
  title: 'KUBot - Live Currency Rates',
  description: 'Real-time currency exchange rates for banks in Uzbekistan',
  icons: {
    icon: '/favicon.ico',
  },
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  themeColor: '#3B82F6',
}

export default function RootLayout({
  children,
}: {
  children: ReactNode
}) {
  return (
    <html lang="en">
      <head>
        <script src="https://telegram.org/js/telegram-web-app.js" async></script>
      </head>
      <body className="antialiased">
        {children}
      </body>
    </html>
  )
}