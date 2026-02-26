export default function Header() {
  return (
    <header className="border-b border-gray-800 bg-gray-900/50 backdrop-blur-sm">
      <div className="max-w-4xl mx-auto px-6 py-4 flex items-center gap-3">
        <div className="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center text-xl font-bold">
          T
        </div>
        <div>
          <h1 className="text-xl font-bold text-white">Trans-Script</h1>
          <p className="text-xs text-gray-400">Tradutor PHP &middot; EN &rarr; PT-BR</p>
        </div>
      </div>
    </header>
  )
}
