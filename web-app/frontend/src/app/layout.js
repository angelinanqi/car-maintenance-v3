import { Provider } from "@/components/ui/provider"


export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <Provider>{children}</Provider>
      </body>
    </html>
  )
}