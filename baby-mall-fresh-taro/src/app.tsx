import '@antmjs/vantui/lib/button/index.css'
import '@antmjs/vantui/lib/cell/index.css'
import '@antmjs/vantui/lib/empty/index.css'
import '@antmjs/vantui/lib/field/index.css'
import '@antmjs/vantui/lib/overlay/index.css'
import '@antmjs/vantui/lib/popup/index.css'
import '@antmjs/vantui/lib/search/index.css'
import '@antmjs/vantui/lib/stepper/index.css'
import '@antmjs/vantui/lib/tag/index.css'
import './styles/vant-local-font.scss'
import './app.scss'

export default function App(props: { children: React.ReactNode }) {
  // ponytail: mini-program app roots do not reliably mount native view siblings; pages own their watermark host.
  return props.children
}
