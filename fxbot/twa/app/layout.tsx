import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'FXBot - Currency Exchange',
  description: 'Currency exchange rates bot Telegram Web App',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <head>
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
      </head>
      <body>
        {children}
      </body>
    </html>
  )
}