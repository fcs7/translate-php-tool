export default function Header({ user, onLogout }) {
  return (
    <header className="border-b border-gray-800 bg-gray-900/50 backdrop-blur-sm">
      <div className="max-w-4xl mx-auto px-6 py-4 flex items-center gap-3">
        <div className="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center text-xl font-bold text-white">
          T
        </div>
        <div className="flex-1">
          <h1 className="text-xl font-bold text-white">Trans-Script</h1>
          <p className="text-xs text-gray-400">Tradutor PHP &middot; EN &rarr; PT-BR</p>
        </div>

        {user && onLogout && (
          <div className="flex items-center gap-3">
            <span className="text-xs text-gray-500 hidden sm:block">{user.email}</span>
            <button
              onClick={onLogout}
              className="text-xs text-gray-400 hover:text-white border border-gray-700
                         hover:border-gray-500 px-3 py-1.5 rounded-lg transition-colors"
            >
              Sair
            </button>
          </div>
        )}
      </div>
    </header>
  )
}
