import { Provider } from "@/components/ui/provider"

export const metadata = {
  title: { default: "Roadie Admin", template: "%s | Roadie Admin" },
  description: "Manage vehicle care, reviewed knowledge and learning content for Roadie.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <Provider>{children}</Provider>
      </body>
    </html>
  )
}
