import { type ReactNode } from 'react'
import './app.scss'

export default function App({ children }: { children: ReactNode }) {
  // ponytail: mini-program app roots do not reliably mount native view siblings; pages own their watermark host.
  return children
}
