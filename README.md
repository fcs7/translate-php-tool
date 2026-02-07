# 🌐 PHP Translation Tool (EN → PT-BR)

Traduz automaticamente arquivos de localização PHP do inglês para português brasileiro.
- 🔄 **Confiável**: Retoma de onde parou se interrompido
- 🛡️ **Seguro**: Preserva placeholders, HTML e formatação

---

## 📥 Instalação

### Passo 1: Baixar o script

```bash
# Clone o repositório
git clone https://github.com/fcs7/trans-script-py.git
cd trans-script-py
```

### Passo 2: Instalar no sistema (Opcional - Recomendado)

**Opção A: Instalar em /usr/local/bin (requer sudo)**
```bash
# Tornar executável
chmod +x translate.py

# Copiar para PATH do sistema
sudo cp translate.py /usr/local/bin/translate-php

# Agora pode usar de qualquer lugar:
translate-php --help
```

**Opção B: Adicionar ao seu PATH pessoal (sem sudo)**
```bash
# Tornar executável
chmod +x translate.py

# Mover para um diretório no seu home
mkdir -p ~/.local/bin
cp translate.py ~/.local/bin/translate-php

# Adicionar ao PATH (adicione essa linha ao final do ~/.bashrc)
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc

# Recarregar configuração
source ~/.bashrc

# Agora pode usar de qualquer lugar:
translate-php --help
```

### Passo 3: Dependências

O script instalará automaticamente o `translate-shell` na primeira execução.

Se preferir instalar manualmente:

```bash
# Debian/Ubuntu
sudo apt install translate-shell

# Fedora/RHEL
sudo dnf install translate-shell

# Arch Linux
sudo pacman -S translate-shell
```

---

## 🚀 Uso

### Modo 1: Auto-detecção (Recomendado) 🎯

**Quando usar:** Não sabe onde estão os arquivos de localização

```bash
# Procura automaticamente em todo o projeto
translate-php --find /var/www/meu-projeto

# O script vai:
# 1. Encontrar diretórios com arquivos PHP de localização
# 2. Detectar o idioma (en, pt-br, es, etc.)
# 3. Perguntar qual diretório traduzir
# 4. Sugerir diretório de saída
# 5. Começar a tradução
```

**Exemplo de uso:**
```bash
$ translate-php --find /var/www/app

🔍 Procurando diretórios de localização em: /var/www/app

📂 Encontrados 1 diretório com arquivos de localização:

  [1] /var/www/app/lang/en [EN]
      └─ 15 arquivos PHP, ~2500 strings
      └─ Exemplos: common.php, interface.php, api.php

Digite o número do diretório [1] (ou 'q' para sair): 1

📁 Diretório selecionado: /var/www/app/lang/en
📁 Sugestão de saída: /var/www/app/lang/br

Usar diretório sugerido? [S/n]: s

🚀 Usando 4 workers paralelos
📁 15 arquivos PHP encontrados

[Processando...]
✅ Completo. 15 arquivos processados.

💾 Cache de traduções:
   - 2847 strings traduzidas no total
   - 1923 traduções únicas no cache
   - 924 reutilizações de cache (32.5% economia)
```

---

### Modo 2: Manual (Quando já sabe os caminhos)

```bash
# Traduzir diretório específico
translate-php --dir-in ./en --dir-out ./br

# Exemplo prático:
translate-php --dir-in /var/www/app/lang/en --dir-out /var/www/app/lang/br
```

---

### Modo 3: Automático (Para scripts e CI/CD)

```bash
# Traduz automaticamente sem perguntar nada
translate-php --find /var/www/app --auto-translate --dir-out /var/www/app/lang/br
```

**Exemplo em script bash:**
```bash
#!/bin/bash
# deploy.sh

echo "Traduzindo localização..."
translate-php --find /var/www/app --auto-translate --dir-out /var/www/app/lang/br

if [ $? -eq 0 ]; then
    echo "✅ Tradução concluída com sucesso!"
else
    echo "❌ Erro na tradução"
    exit 1
fi
```

---

## ⚙️ Opções

| Opção | Descrição | Exemplo |
|-------|-----------|---------|
| `--find PATH` | Busca automática de diretórios | `--find /var/www` |
| `--dir-in DIR` | Diretório de entrada (EN) | `--dir-in ./en` |
| `--dir-out DIR` | Diretório de saída (BR) | `--dir-out ./br` |
| `--auto-translate` | Traduz sem confirmação | Usado com `--find` |
| `--delay N` | Delay entre traduções (padrão: 0.2s) | `--delay 0.1` |
| `--validate` | Apenas valida tradução existente | `--validate` |

---

## ⚡ Performance

**Com cache + paralelização:**
- 1.000 strings → ~5 minutos
- 10.000 strings → ~30-40 minutos
- 50.000 strings → ~2-3 horas

**Velocidade: 10-20x mais rápido que tradução linha por linha!**

O script:
- Usa cache para evitar re-traduzir strings duplicadas
- Processa múltiplos arquivos em paralelo (4 workers)
- Retoma automaticamente se interrompido (Ctrl+C)

---

## 📁 Estrutura de Arquivos

O script mantém a estrutura de diretórios:

```
Entrada:                  Saída:
en/                       br/
├── common.php           ├── common.php
├── interface.php        ├── interface.php
└── modules/             └── modules/
    └── api.php              └── api.php
```

---

## ❓ Problemas Comuns

### "translate-shell não encontrado"

```bash
# Instale manualmente (escolha seu sistema):
sudo apt install translate-shell        # Debian/Ubuntu
sudo dnf install translate-shell        # Fedora/RHEL
sudo pacman -S translate-shell          # Arch Linux
```

### "Nenhum diretório encontrado"

```bash
# Aumente a profundidade da busca
translate-php --find /var/www --max-depth 10

# Ou verifique manualmente:
grep -r '\$msg_arr' /var/www --include="*.php"
```

### Script muito lento / Rate limiting

```bash
# Aumente o delay entre traduções
translate-php --dir-in ./en --dir-out ./br --delay 0.5
```

### Retomar tradução interrompida

```bash
# Simplesmente execute novamente o mesmo comando
# O script continuará de onde parou automaticamente
translate-php --dir-in ./en --dir-out ./br
```

---

## 🔧 Exemplos Práticos

### Exemplo 1: Projeto novo

```bash
# 1. Entrar no diretório do projeto
cd /var/www/meu-projeto

# 2. Encontrar e traduzir
translate-php --find .

# 3. Seguir as instruções na tela
```

### Exemplo 2: Atualizar tradução existente

```bash
# Se já traduziu antes e quer atualizar:
translate-php --dir-in ./lang/en --dir-out ./lang/br

# O script vai:
# - Pular arquivos já completos
# - Retomar arquivos incompletos
# - Traduzir apenas novos arquivos
```

### Exemplo 3: CI/CD (GitLab/GitHub Actions)

```yaml
# .gitlab-ci.yml
translate-to-br:
  stage: build
  script:
    - git clone https://github.com/fcs7/trans-script-py.git
    - cd trans-script-py
    - python3 translate.py --find /app/lang --auto-translate --dir-out /app/lang/br
    - find /app/lang/br -name '*.php' -exec php -l {} \;  # Validar sintaxe
  artifacts:
    paths:
      - app/lang/br/
```

---

## 🆘 Precisa de Ajuda?

```bash
# Ver todas as opções
translate-php --help

# Reportar problemas
https://github.com/fcs7/trans-script-py/issues
```

---

## 📝 Changelog

### v2.2 - Multiprocessing (2026-02-07)
- ✅ **Processamento paralelo**: 4 workers simultâneos
- ✅ **Cache compartilhado**: Workers compartilham traduções
- ✅ **10-20x mais rápido** que versão original

### v2.1 - Cache Inteligente (2026-02-07)
- ✅ Cache de traduções duplicadas
- ✅ Delay otimizado (0.2s)
- ✅ Estatísticas de cache

### v2.0 - Auto-detecção
- ✅ Busca automática de diretórios
- ✅ Detecção de idioma
- ✅ Modo interativo e automático

### v1.0 - Release Inicial
- ✅ Tradução EN → PT-BR
- ✅ Proteção de placeholders
- ✅ Sistema de resume

---

**Desenvolvido para facilitar a localização de projetos PHP** 🚀

Licença: MIT
