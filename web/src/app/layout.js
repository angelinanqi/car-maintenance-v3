import { Provider } from "@/components/ui/provider"

export const metadata = {
  title: { default: "MyRoadie Admin", template: "%s | MyRoadie Admin" },
  description: "Manage vehicle care, reviewed knowledge and learning content for MyRoadie.",
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
