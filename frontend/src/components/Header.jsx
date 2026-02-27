export default function Header({ user, onLogout }) {
  const quota = user?.quota

  const quotaColor = !quota ? 'bg-blue-500'
    : quota.percent > 95 ? 'bg-red-500'
    : quota.percent > 80 ? 'bg-yellow-500'
    : 'bg-blue-500'

  return (
    <header className="border-b border-gray-800 bg-gray-900/50 backdrop-blur-sm">
      <div className="max-w-4xl mx-auto px-6 py-4 flex items-center gap-3">
        <div className="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center text-xl font-bold text-white">
          T
        </div>
        <div className="flex-1">
          <h1 className="text-xl font-bold text-white">Tradutor</h1>
        </div>

        {user && onLogout && (
          <div className="flex items-center gap-3">
            {quota && (
              <div className="hidden sm:flex items-center gap-2">
                <div className="w-20 bg-gray-800 rounded-full h-1.5 overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${quotaColor}`}
                    style={{ width: `${Math.min(quota.percent, 100)}%` }}
                  />
                </div>
                <span className="text-xs text-gray-500 whitespace-nowrap">
                  {quota.used_mb} / {quota.limit_mb} MB
                </span>
              </div>
            )}
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