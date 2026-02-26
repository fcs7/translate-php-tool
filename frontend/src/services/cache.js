/**
 * Cache simples com TTL usando localStorage.
 *
 * - Não armazena tokens nem dados sensíveis — apenas dados não-confidenciais
 *   do usuário (id, email) para eliminar o spinner de carregamento inicial.
 * - Resiliente: falha silenciosamente em modo privado ou quota excedida.
 * - Todas as chaves levam o prefixo `ts_` para isolar do restante do site.
 */

const PREFIX = 'ts_'

/**
 * Salva um valor no cache com tempo de vida (TTL).
 * @param {string} key
 * @param {*} value  — valor serializável em JSON
 * @param {number} ttlMs — duração em ms (padrão: 5 min)
 */
export function setCache(key, value, ttlMs = 5 * 60 * 1000) {
  try {
    localStorage.setItem(PREFIX + key, JSON.stringify({
      v: value,
      exp: Date.now() + ttlMs,
    }))
  } catch {
    // localStorage indisponível (modo privado, quota excedida, etc.)
  }
}

/**
 * Busca um valor do cache. Retorna null se ausente ou expirado.
 * @param {string} key
 * @returns {*|null}
 */
export function getCache(key) {
  try {
    const raw = localStorage.getItem(PREFIX + key)
    if (!raw) return null
    const entry = JSON.parse(raw)
    if (Date.now() > entry.exp) {
      localStorage.removeItem(PREFIX + key)
      return null
    }
    return entry.v
  } catch {
    return null
  }
}

/**
 * Remove uma entrada específica do cache.
 * @param {string} key
 */
export function clearCache(key) {
  try {
    localStorage.removeItem(PREFIX + key)
  } catch {}
}

/**
 * Remove todas as entradas desta app do localStorage.
 * Chamado no logout para garantir que nenhum dado persiste.
 */
export function clearAllCache() {
  try {
    Object.keys(localStorage)
      .filter(k => k.startsWith(PREFIX))
      .forEach(k => localStorage.removeItem(k))
  } catch {}
}
