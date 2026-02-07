# PHP Translation Tool (EN → PT-BR)

Ferramenta automática para traduzir arquivos de localização PHP do inglês para português brasileiro usando [translate-shell](https://github.com/soimort/translate-shell).

## 📋 Características

- ✅ **Auto-detecção** de diretórios de localização em projetos
- ✅ **3 modos de operação**: manual, interativo e automático
- ✅ Traduz apenas os **valores** das strings (lado direito do `=`)
- ✅ Preserva **chaves**, **estrutura** e **formatação** do código
- ✅ Protege **placeholders** como `{variable_name}` (não são traduzidos)
- ✅ Mantém **HTML** e **escapes** PHP (`\'`, `\"`, `\n`) intactos
- ✅ **Resume automático**: se interrompido, continua de onde parou
- ✅ **Auto-instalação** do translate-shell de acordo com o sistema
- ✅ Detecta idioma automaticamente pelo nome do diretório

## 🚀 Instalação

```bash
# Baixe o script
wget https://raw.githubusercontent.com/fcs7/trans-script-py/main/translate.py
chmod +x translate.py

# OU clone o repositório
git clone https://github.com/fcs7/trans-script-py.git
cd trans-script-py
```

**Dependências**: Python 3.6+ (já vem na maioria dos sistemas Linux)

O script detecta automaticamente seu sistema e instala o `translate-shell` se necessário:
- **Debian/Ubuntu**: `apt`
- **RHEL/Fedora/CentOS**: `dnf` ou `yum`
- **Arch Linux**: `pacman`
- **openSUSE**: `zypper`
- **macOS**: `brew`

## 📖 Uso

### Modo 1: Auto-detecção Interativa (Recomendado) 🆕

Ideal quando você não sabe onde estão os arquivos de localização:

```bash
python3 translate.py --find /var/www/meu-projeto
```

**O que acontece:**
1. 🔍 Busca recursivamente por diretórios com arquivos PHP de localização
2. 📊 Mostra lista de candidatos com estatísticas (número de arquivos, strings)
3. 🎯 Detecta automaticamente idioma (EN, PT-BR, ES, FR, etc.)
4. ✨ Permite escolher interativamente qual diretório traduzir
5. 💡 Sugere automaticamente o diretório de saída

**Exemplo de saída:**
```
🔍 Procurando diretórios de localização em: /var/www/app

📂 Encontrados 2 diretórios com arquivos de localização:

  [1] /var/www/app/lang/en [EN]
      └─ 15 arquivos PHP, ~2500 strings
      └─ Exemplos: common.php, interface.php, api.php

  [2] /var/www/app/lang/es [ES]
      └─ 15 arquivos PHP, ~2400 strings
      └─ Exemplos: common.php, interface.php, api.php

Digite o número do diretório de entrada [1-2] (ou 'q' para sair): 1

📁 Diretório de entrada selecionado: /var/www/app/lang/en
📁 Sugestão de saída: /var/www/app/lang/br

Usar diretório sugerido? [S/n]: s
```

### Modo 2: Auto-detecção Automática (CI/CD) 🆕

Para scripts automatizados e CI/CD:

```bash
python3 translate.py --find /var/www/app --auto-translate --dir-out ./br_translated
```

**Requer:**
- Exatamente **1 diretório EN** detectado
- `--dir-out` especificado
- Não pede confirmação

### Modo 3: Manual (Clássico)

Quando você já sabe os caminhos:

```bash
python3 translate.py --dir-in ./en --dir-out ./br
```

## 📝 Parâmetros

### Modo Manual

| Parâmetro | Descrição | Exemplo |
|-----------|-----------|---------|
| `--dir-in` | Diretório de entrada (inglês) | `--dir-in ./en` |
| `--dir-out` | Diretório de saída (traduzido) | `--dir-out ./br` |

### Modo Auto-detecção 🆕

| Parâmetro | Descrição | Padrão |
|-----------|-----------|--------|
| `--find PATH` | Busca recursiva a partir deste caminho | - |
| `--auto-translate` | Traduz automaticamente sem interação | `false` |
| `--max-depth N` | Profundidade máxima da busca | `5` |
| `--dir-out` | (Obrigatório com --auto-translate) | - |

### Opções Gerais

| Parâmetro | Descrição | Padrão |
|-----------|-----------|--------|
| `--delay N` | Segundos entre traduções | `0.5` |

## 💡 Exemplos Práticos

### Exemplo 1: Descobrir onde estão os arquivos

```bash
# Busca em todo o projeto web
python3 translate.py --find /var/www

# Busca apenas em um subdiretório
python3 translate.py --find ~/meu-app/src
```

### Exemplo 2: Tradução interativa

```bash
# Busca, escolhe e traduz interativamente
python3 translate.py --find /var/www/app

# Com delay customizado
python3 translate.py --find /var/www/app --delay 0.3
```

### Exemplo 3: CI/CD automatizado

```bash
# Para pipelines GitLab/GitHub Actions
python3 translate.py \
  --find /app \
  --auto-translate \
  --dir-out /app/lang/br \
  --delay 0.2
```

### Exemplo 4: Vários idiomas, várias versões

```bash
# Encontrar e traduzir múltiplos projetos
for project in /var/www/*/; do
  python3 translate.py --find "$project" --auto-translate --dir-out "${project}/lang/br"
done
```

## 📁 Estrutura de arquivos

O script preserva a estrutura de diretórios:

```
Entrada (--dir-in):          Saída (--dir-out):
en/                          br/
├── common.php               ├── common.php
├── interface.php            ├── interface.php
└── api/                     └── api/
    ├── REST/                    ├── REST/
    │   └── lang.php             │   └── lang.php
    └── soap/                    └── soap/
        └── lang.php                 └── lang.php
```

## 🔧 Como funciona

### Detecção automática de diretórios 🆕

A busca procura por diretórios que:
- ✅ Contêm arquivos `.php`
- ✅ Têm pelo menos 5 ocorrências de `$msg_arr`
- ✅ Não são diretórios de sistema (`node_modules`, `.git`, `vendor`, etc.)

Detecta idioma automaticamente:
- `en`, `english`, `en_us`, `en-us` → **EN**
- `br`, `pt-br`, `pt_br`, `portuguese` → **PT-BR**
- `es`, `spanish`, `español` → **ES**
- `fr`, `french`, `français` → **FR**
- `de`, `german`, `deutsch` → **DE**
- `it`, `italian`, `italiano` → **IT**

### Formato reconhecido

```php
$msg_arr['chave'] = 'valor em inglês';
```

### Processo de tradução

```
1. Entrada:
   $msg_arr['btn_save'] = 'Save changes';

2. Extrai valor: "Save changes"

3. Protege placeholders: "Save changes" (sem {})

4. Traduz: "Salvar alterações"

5. Reconstrói:
   $msg_arr['btn_save'] = 'Salvar alterações';
```

### Casos especiais tratados

#### ✅ Aspas escapadas
```php
// Entrada
$msg_arr['key'] = 'The \'Maximum\' value must be a number';

// Saída
$msg_arr['key'] = 'O valor \'Máximo\' deve ser um número';
```

#### ✅ Placeholders preservados
```php
// Entrada
$msg_arr['msg'] = 'User {username} has {count} messages';

// Saída
$msg_arr['msg'] = 'Usuário {username} tem {count} mensagens';
```

#### ✅ HTML mantido
```php
// Entrada
$msg_arr['alert'] = '<b>Warning:</b> This action cannot be undone';

// Saída
$msg_arr['alert'] = '<b>Aviso:</b> Esta ação não pode ser desfeita';
```

#### ✅ Linhas não-traduzíveis copiadas
```php
<?php
// Este comentário não é traduzido
$msg_arr = array();
define('CONSTANT', 'value');
?>
```

## ⚡ Performance

- **Delay padrão**: 0.5s entre traduções
- **Estimativa**: ~10.000 strings levam aproximadamente 1.5 horas
- **Resume**: Ctrl+C para pausar, execute novamente para continuar

### Ajustando a velocidade

```bash
# Mais rápido (pode causar rate limiting)
--delay 0.2

# Mais lento (mais seguro)
--delay 1.0
```

## 🛠️ Troubleshooting

### Erro: "translate-shell não encontrado"

O script tenta instalar automaticamente. Se falhar:

```bash
# Instalação manual - Debian/Ubuntu
sudo apt install translate-shell

# Instalação manual - Fedora/RHEL
sudo dnf install translate-shell

# Instalação manual - Arch
sudo pacman -S translate-shell

# Verificar instalação
trans --version
```

### Nenhum diretório encontrado com --find

```bash
# Aumentar profundidade da busca
python3 translate.py --find /var/www --max-depth 10

# Verificar manualmente se há arquivos PHP com $msg_arr
grep -r '\$msg_arr' /var/www --include="*.php"
```

### Erro: "Caminho não encontrado"

Verifique se o caminho está correto:

```bash
ls -la ~/Documentos/en  # Deve listar os arquivos .php
```

### Traduções incorretas

- Aumente o `--delay` para evitar rate limiting
- Verifique sua conexão de internet
- O Google Translate (usado pelo translate-shell) pode ter limitações temporárias

### Script muito lento

Arquivo grande (`interface.php` com 8.000+ linhas) é normal:

```bash
# Monitore o progresso
python3 translate.py --dir-in ./en --dir-out ./br

# Saída mostra progresso a cada 50 strings:
[50] linha 125/8868
[100] linha 250/8868
...
```

## ✅ Verificação pós-tradução

```bash
# 1. Verificar se todos arquivos foram criados
diff <(find en -name '*.php' | sort) \
     <(find br -name '*.php' | sed 's|br/|en/|' | sort)

# 2. Comparar contagem de linhas (devem ser iguais)
wc -l en/*.php
wc -l br/*.php

# 3. Verificar sintaxe PHP
find br -name '*.php' -exec php -l {} \;

# 4. Checar se placeholders não vazaram
grep -r '__PH' br/
# (não deve retornar nada)
```

## 📝 Exemplo completo

### Cenário: Projeto web desconhecido

```bash
# 1. Descobrir onde estão os arquivos de localização
python3 translate.py --find /var/www/meu-projeto

# 2. Script mostra:
#    [1] /var/www/meu-projeto/includes/lang/en [EN]
#        └─ 20 arquivos PHP, ~3000 strings

# 3. Escolher opção 1 e confirmar sugestão de saída

# 4. Aguardar conclusão (pode levar tempo)

# 5. Verificar resultado
php -l /var/www/meu-projeto/includes/lang/br/interface.php
```

### Cenário: CI/CD Pipeline

```yaml
# .gitlab-ci.yml
translate-to-br:
  stage: build
  script:
    - python3 translate.py --find /app/lang --auto-translate --dir-out /app/lang/br --delay 0.3
    - find /app/lang/br -name '*.php' -exec php -l {} \;
  artifacts:
    paths:
      - app/lang/br/
```

## 🤝 Contribuindo

Melhorias são bem-vindas:

1. Fork o repositório
2. Crie uma branch: `git checkout -b minha-feature`
3. Commit: `git commit -am 'Adiciona nova feature'`
4. Push: `git push origin minha-feature`
5. Abra um Pull Request

## 📄 Licença

MIT License - sinta-se livre para usar e modificar.

## 🔗 Links úteis

- [translate-shell](https://github.com/soimort/translate-shell) - Ferramenta de tradução via CLI
- [Google Translate API](https://translate.google.com) - Engine de tradução (usado pelo translate-shell)
- [Repositório GitHub](https://github.com/fcs7/trans-script-py)

## ⚠️ Avisos

- **Revisão recomendada**: Traduções automáticas podem conter erros ou imprecisões
- **Rate limiting**: Google Translate pode bloquear temporariamente após muitas requisições
- **Contexto**: O tradutor não entende contexto de software, revise termos técnicos
- **Backup**: Sempre mantenha backup dos arquivos originais
- **Auto-detecção**: O modo `--find` ignora diretórios de sistema automaticamente, mas pode encontrar falsos positivos

## 🆕 Changelog

### v2.0 - Auto-detecção de diretórios
- ✅ Modo `--find` para busca recursiva
- ✅ Detecção automática de idioma
- ✅ Modo interativo com seleção
- ✅ Modo `--auto-translate` para CI/CD
- ✅ Sugestão inteligente de diretório de saída

### v1.0 - Release inicial
- ✅ Tradução EN → PT-BR
- ✅ Proteção de placeholders
- ✅ Resume automático
- ✅ Auto-instalação do translate-shell

---

**Desenvolvido para facilitar a localização de projetos PHP** 🚀
