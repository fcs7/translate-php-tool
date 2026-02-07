#!/usr/bin/env python3
"""
Script de tradução EN → PT-BR para arquivos PHP de localização.
Usa translate-shell (trans) para traduzir os valores de $msg_arr.
Suporta resume: se interrompido, continua de onde parou.

Uso:
  python3 translate.py --dir-in ./en --dir-out ./br
  python3 translate.py --dir-in /caminho/entrada --dir-out /caminho/saida --delay 0.3
  python3 translate.py --find /var/www                # Auto-detecta diretórios
  python3 translate.py --find /var/www --auto-translate  # Detecta e traduz
"""

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
import time

# === Configuração padrão ===
SOURCE_LANG = 'en'
TARGET_LANG = 'pt-br'
DEFAULT_DELAY = 0.5

# === Regex ===
SINGLE_QUOTE_RE = re.compile(
    r"^(\$msg_arr\[.*?\]\s*=\s*')((?:[^'\\]|\\.)*)(';\s*;?\s*)$"
)
DOUBLE_QUOTE_RE = re.compile(
    r'^(\$msg_arr\[.*?\]\s*=\s*")((?:[^"\\]|\\.)*)(";?\s*;?\s*)$'
)
PLACEHOLDER_RE = re.compile(r'\{[a-zA-Z_][a-zA-Z0-9_]*\}')


# =============================================================================
# Auto-detecção de diretórios de localização
# =============================================================================

def find_lang_dirs(root_path, max_depth=5):
    """
    Busca recursivamente por diretórios que contêm arquivos PHP de localização.
    Retorna lista de tuplas (dir_path, file_count, sample_files).
    """
    candidates = []
    root_path = os.path.abspath(os.path.expanduser(root_path))

    print(f"🔍 Procurando diretórios de localização em: {root_path}")
    print(f"   (profundidade máxima: {max_depth})\n")

    for dirpath, dirnames, filenames in os.walk(root_path):
        # Calcular profundidade
        depth = dirpath[len(root_path):].count(os.sep)
        if depth > max_depth:
            dirnames[:] = []  # Não descer mais
            continue

        # Ignorar diretórios comuns que não são de localização
        dirnames[:] = [d for d in dirnames if d not in [
            'node_modules', '.git', 'vendor', 'cache', 'tmp', 'temp',
            'build', 'dist', 'test', 'tests', '__pycache__'
        ]]

        php_files = [f for f in filenames if f.endswith('.php')]
        if not php_files:
            continue

        # Verificar se algum arquivo contém $msg_arr
        msg_arr_count = 0
        sample_files = []

        for php_file in php_files[:10]:  # Checar até 10 arquivos
            file_path = os.path.join(dirpath, php_file)
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read(5000)  # Ler primeiros 5KB
                    matches = content.count('$msg_arr')
                    if matches > 0:
                        msg_arr_count += matches
                        sample_files.append(php_file)
            except:
                continue

        if msg_arr_count >= 5:  # Mínimo de 5 ocorrências de $msg_arr
            candidates.append({
                'path': dirpath,
                'msg_count': msg_arr_count,
                'php_files': len(php_files),
                'samples': sample_files[:3]
            })

    return candidates


def detect_language_from_path(path):
    """Tenta detectar o idioma baseado no nome do diretório."""
    path_lower = path.lower()

    lang_patterns = {
        'en': ['en', 'english', 'en_us', 'en-us', 'eng'],
        'pt-br': ['br', 'pt-br', 'pt_br', 'portuguese', 'brasil', 'brazil'],
        'es': ['es', 'spanish', 'español', 'espanol'],
        'fr': ['fr', 'french', 'français', 'francais'],
        'de': ['de', 'german', 'deutsch'],
        'it': ['it', 'italian', 'italiano'],
    }

    for lang, patterns in lang_patterns.items():
        for pattern in patterns:
            if f'/{pattern}/' in path_lower or path_lower.endswith(f'/{pattern}'):
                return lang

    return 'unknown'


def suggest_output_dir(input_dir, target_lang='pt-br'):
    """Sugere um diretório de saída baseado no diretório de entrada."""
    parent = os.path.dirname(input_dir)
    basename = os.path.basename(input_dir)

    # Se o diretório termina com 'en', sugerir 'br'
    if basename.lower() in ['en', 'english', 'en_us', 'en-us']:
        return os.path.join(parent, 'br')

    # Caso contrário, adicionar sufixo
    return input_dir + '_br'


def interactive_select_dir(candidates):
    """Permite o usuário selecionar interativamente o diretório."""
    if not candidates:
        print("❌ Nenhum diretório de localização encontrado.")
        return None

    print(f"\n📂 Encontrados {len(candidates)} diretórios com arquivos de localização:\n")

    for i, cand in enumerate(candidates, 1):
        lang = detect_language_from_path(cand['path'])
        lang_info = f" [{lang.upper()}]" if lang != 'unknown' else ""

        print(f"  [{i}] {cand['path']}{lang_info}")
        print(f"      └─ {cand['php_files']} arquivos PHP, ~{cand['msg_count']} strings")
        print(f"      └─ Exemplos: {', '.join(cand['samples'])}")
        print()

    while True:
        try:
            choice = input("Digite o número do diretório de entrada [1-{}] (ou 'q' para sair): ".format(len(candidates)))
            if choice.lower() == 'q':
                return None

            idx = int(choice) - 1
            if 0 <= idx < len(candidates):
                return candidates[idx]['path']
            else:
                print("❌ Número inválido. Tente novamente.")
        except (ValueError, KeyboardInterrupt):
            print("\n❌ Cancelado.")
            return None


# =============================================================================
# Detecção de sistema e auto-instalação do translate-shell
# =============================================================================

def detect_pkg_manager():
    """Detecta o gerenciador de pacotes do sistema."""
    managers = [
        ('apt',    ['sudo', 'apt', 'install', '-y', 'translate-shell']),
        ('dnf',    ['sudo', 'dnf', 'install', '-y', 'translate-shell']),
        ('yum',    ['sudo', 'yum', 'install', '-y', 'translate-shell']),
        ('pacman', ['sudo', 'pacman', '-S', '--noconfirm', 'translate-shell']),
        ('zypper', ['sudo', 'zypper', 'install', '-y', 'translate-shell']),
        ('brew',   ['brew', 'install', 'translate-shell']),
    ]
    for name, cmd in managers:
        if shutil.which(name):
            return name, cmd
    return None, None


def install_trans():
    """Instala translate-shell automaticamente de acordo com o sistema."""
    pkg_name, install_cmd = detect_pkg_manager()

    if not pkg_name:
        print("ERRO: Não foi possível detectar o gerenciador de pacotes.")
        print("Instale o translate-shell manualmente:")
        print("  https://github.com/soimort/translate-shell")
        sys.exit(1)

    print(f"translate-shell não encontrado. Instalando via {pkg_name}...")
    print(f"  Executando: {' '.join(install_cmd)}")

    try:
        subprocess.run(install_cmd, check=True)
        print("translate-shell instalado com sucesso!")
    except subprocess.CalledProcessError:
        print(f"ERRO: Falha ao instalar via {pkg_name}.")
        print("Tente instalar manualmente:")
        print("  https://github.com/soimort/translate-shell")
        sys.exit(1)


def ensure_trans():
    """Garante que o comando 'trans' está disponível."""
    if shutil.which('trans'):
        return
    install_trans()
    if not shutil.which('trans'):
        print("ERRO: 'trans' ainda não encontrado após instalação.")
        sys.exit(1)


# =============================================================================
# Funções de tradução
# =============================================================================

def protect_placeholders(text):
    """Substitui {placeholder} por tokens opacos antes da tradução."""
    mapping = {}
    counter = [0]

    def replacer(match):
        token = f"__PH{counter[0]}__"
        mapping[token] = match.group(0)
        counter[0] += 1
        return token

    protected = PLACEHOLDER_RE.sub(replacer, text)
    return protected, mapping


def restore_placeholders(text, mapping):
    """Restaura tokens opacos de volta para {placeholder}."""
    for token, original in mapping.items():
        text = text.replace(token, original)
    return text


def prepare_for_translation(value, quote_char):
    """Remove escapes PHP para obter texto natural para tradução."""
    if quote_char == "'":
        return value.replace("\\'", "'").replace("\\\\", "\\")
    else:
        return value.replace('\\"', '"')


def re_escape(translated, quote_char):
    """Reaplica escapes PHP após tradução."""
    if quote_char == "'":
        translated = translated.replace("\\", "\\\\")
        translated = translated.replace("'", "\\'")
    else:
        translated = translated.replace('"', '\\"')
    return translated


def translate_text(text, delay):
    """Traduz texto usando trans -b en:pt-br. Retry 1x em caso de falha."""
    if not text.strip():
        return text

    for attempt in range(2):
        try:
            result = subprocess.run(
                ['trans', '-b', f'{SOURCE_LANG}:{TARGET_LANG}', text],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except subprocess.TimeoutExpired:
            pass

        if attempt == 0:
            time.sleep(2)

    print(f"  AVISO: falha na tradução, mantendo original: {text[:60]}")
    return text


# =============================================================================
# Processamento de arquivos
# =============================================================================

def process_file(src_path, dst_path, dst_dir, delay):
    """Lê arquivo PHP, traduz valores de $msg_arr, escreve no destino."""
    with open(src_path, 'r', encoding='utf-8') as f:
        src_lines = f.readlines()

    total_lines = len(src_lines)

    # Resume: checar se já existe saída parcial
    start_line = 0
    if os.path.exists(dst_path):
        with open(dst_path, 'r', encoding='utf-8') as f:
            existing = f.readlines()
        start_line = len(existing)
        if start_line >= total_lines:
            print(f"  Pulando (já completo): {os.path.relpath(dst_path, dst_dir)}")
            return
        print(f"  Resumindo da linha {start_line + 1}/{total_lines}")
    else:
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)

    mode = 'a' if start_line > 0 else 'w'
    translated_count = 0

    with open(dst_path, mode, encoding='utf-8') as out:
        for i in range(start_line, total_lines):
            line = src_lines[i]
            stripped = line.rstrip('\n')

            m = SINGLE_QUOTE_RE.match(stripped)
            quote_char = "'"

            if not m:
                m = DOUBLE_QUOTE_RE.match(stripped)
                quote_char = '"'

            if m:
                prefix = m.group(1)
                raw_value = m.group(2)
                suffix = m.group(3)

                text = prepare_for_translation(raw_value, quote_char)
                text, ph_map = protect_placeholders(text)
                translated = translate_text(text, delay)
                translated = restore_placeholders(translated, ph_map)
                translated = re_escape(translated, quote_char)

                out.write(prefix + translated + suffix + '\n')
                translated_count += 1

                if translated_count % 50 == 0:
                    print(f"  [{translated_count}] linha {i + 1}/{total_lines}")

                time.sleep(delay)
            else:
                out.write(line)

            out.flush()

    print(f"  Concluído: {translated_count} strings traduzidas")


# =============================================================================
# Validação e Verificação
# =============================================================================

def validate_translation(src_dir, dst_dir):
    """
    Valida a qualidade da tradução comparando EN vs BR.
    Retorna dict com estatísticas e lista de problemas.
    """
    stats = {
        'success': 0,
        'untranslated': 0,
        'missing_placeholders': 0,
        'escape_issues': 0,
        'line_mismatch': 0,
        'missing_files': 0,
    }
    issues = []

    print("\n" + "="*60)
    print("🔍 VALIDANDO TRADUÇÃO...")
    print("="*60 + "\n")

    # Coletar todos arquivos .php do src
    src_files = []
    for dirpath, dirnames, filenames in os.walk(src_dir):
        for filename in filenames:
            if filename.endswith('.php'):
                src_path = os.path.join(dirpath, filename)
                rel_path = os.path.relpath(src_path, src_dir)
                src_files.append(rel_path)

    for rel_path in sorted(src_files):
        src_path = os.path.join(src_dir, rel_path)
        dst_path = os.path.join(dst_dir, rel_path)

        # Checar se arquivo traduzido existe
        if not os.path.exists(dst_path):
            stats['missing_files'] += 1
            issues.append({
                'type': 'missing_file',
                'file': rel_path,
                'msg': 'Arquivo não foi traduzido'
            })
            continue

        # Ler ambos arquivos
        try:
            with open(src_path, 'r', encoding='utf-8') as f:
                src_lines = f.readlines()
            with open(dst_path, 'r', encoding='utf-8') as f:
                dst_lines = f.readlines()
        except Exception as e:
            issues.append({
                'type': 'read_error',
                'file': rel_path,
                'msg': f'Erro ao ler: {e}'
            })
            continue

        # Verificar contagem de linhas
        if len(src_lines) != len(dst_lines):
            stats['line_mismatch'] += 1
            issues.append({
                'type': 'line_count',
                'file': rel_path,
                'msg': f'Linhas diferentes: EN={len(src_lines)} BR={len(dst_lines)}'
            })

        # Comparar linha por linha
        for i, (src_line, dst_line) in enumerate(zip(src_lines, dst_lines), 1):
            src_m = SINGLE_QUOTE_RE.match(src_line.rstrip('\n')) or \
                    DOUBLE_QUOTE_RE.match(src_line.rstrip('\n'))
            dst_m = SINGLE_QUOTE_RE.match(dst_line.rstrip('\n')) or \
                    DOUBLE_QUOTE_RE.match(dst_line.rstrip('\n'))

            if not src_m or not dst_m:
                continue  # Linha não é $msg_arr

            src_key = src_m.group(1)  # prefix com chave
            src_val = src_m.group(2)
            dst_key = dst_m.group(1)
            dst_val = dst_m.group(2)

            # Checar se chave foi mantida
            if src_key != dst_key:
                issues.append({
                    'type': 'key_changed',
                    'file': rel_path,
                    'line': i,
                    'msg': f'Chave alterada: {src_key[:30]} != {dst_key[:30]}'
                })
                continue

            # Extrair placeholders de ambos
            src_placeholders = set(PLACEHOLDER_RE.findall(src_val))
            dst_placeholders = set(PLACEHOLDER_RE.findall(dst_val))

            # Checar se string foi traduzida (heurística: não pode ser idêntica se tiver texto)
            if src_val == dst_val and len(src_val) > 10 and '{' not in src_val:
                stats['untranslated'] += 1
                issues.append({
                    'type': 'untranslated',
                    'file': rel_path,
                    'line': i,
                    'en': src_val[:50],
                    'br': dst_val[:50]
                })
                continue

            # Checar se placeholders foram preservados
            if src_placeholders != dst_placeholders:
                stats['missing_placeholders'] += 1
                missing = src_placeholders - dst_placeholders
                extra = dst_placeholders - src_placeholders
                issues.append({
                    'type': 'placeholder',
                    'file': rel_path,
                    'line': i,
                    'missing': list(missing),
                    'extra': list(extra),
                    'en': src_val[:50],
                    'br': dst_val[:50]
                })
                continue

            # Checar escapes básicos (contar \' e \")
            src_escapes = src_val.count("\\'") + src_val.count('\\"')
            dst_escapes = dst_val.count("\\'") + dst_val.count('\\"')

            # Se EN tinha escapes e BR não tem nenhum, pode ser problema
            if src_escapes > 0 and dst_escapes == 0 and len(dst_val) > 5:
                stats['escape_issues'] += 1
                issues.append({
                    'type': 'escape',
                    'file': rel_path,
                    'line': i,
                    'msg': f'Possível perda de escape: EN tinha {src_escapes}, BR tem {dst_escapes}',
                    'en': src_val[:50],
                    'br': dst_val[:50]
                })
                continue

            stats['success'] += 1

    # Relatório final
    print(f"📊 ESTATÍSTICAS:\n")
    print(f"  ✅ Traduções OK:          {stats['success']}")
    print(f"  ❌ Não traduzidas:        {stats['untranslated']}")
    print(f"  ⚠️  Placeholders perdidos: {stats['missing_placeholders']}")
    print(f"  ⚠️  Problemas de escape:   {stats['escape_issues']}")
    print(f"  ❌ Arquivos faltando:     {stats['missing_files']}")
    print(f"  ❌ Linhas diferentes:     {stats['line_mismatch']}")

    total_issues = stats['untranslated'] + stats['missing_placeholders'] + \
                   stats['escape_issues'] + stats['missing_files'] + stats['line_mismatch']

    if total_issues == 0:
        print(f"\n🎉 PERFEITO! Nenhum problema encontrado.")
    else:
        print(f"\n⚠️  Total de problemas: {total_issues}")
        print(f"\n❗ PRIMEIROS 20 PROBLEMAS:\n")

        for issue in issues[:20]:
            if issue['type'] == 'untranslated':
                print(f"  ❌ {issue['file']}:{issue['line']}")
                print(f"     String não foi traduzida:")
                print(f"     EN: {issue['en']}")
                print()
            elif issue['type'] == 'placeholder':
                print(f"  ⚠️  {issue['file']}:{issue['line']}")
                print(f"     Placeholders diferentes:")
                if issue['missing']:
                    print(f"     Faltando: {', '.join(issue['missing'])}")
                if issue['extra']:
                    print(f"     Extras: {', '.join(issue['extra'])}")
                print(f"     EN: {issue['en']}")
                print(f"     BR: {issue['br']}")
                print()
            elif issue['type'] == 'escape':
                print(f"  ⚠️  {issue['file']}:{issue['line']}")
                print(f"     {issue['msg']}")
                print(f"     EN: {issue['en']}")
                print(f"     BR: {issue['br']}")
                print()
            elif issue['type'] == 'missing_file':
                print(f"  ❌ {issue['file']}")
                print(f"     {issue['msg']}")
                print()
            elif issue['type'] == 'line_count':
                print(f"  ❌ {issue['file']}")
                print(f"     {issue['msg']}")
                print()

        if len(issues) > 20:
            print(f"  ... e mais {len(issues) - 20} problemas.")

    print("\n" + "="*60 + "\n")

    return stats, issues


# =============================================================================
# Main
# =============================================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description='Traduz arquivos PHP de localização (EN → PT-BR) usando translate-shell.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Modo manual (especificar diretórios)
  %(prog)s --dir-in ./en --dir-out ./br

  # Modo auto-detecção (busca e escolhe interativamente)
  %(prog)s --find /var/www/app

  # Modo auto-detecção + tradução automática
  %(prog)s --find /var/www/app --auto-translate --dir-out ./br_translated
"""
    )

    # Grupo 1: Modo manual
    manual = parser.add_argument_group('modo manual')
    manual.add_argument(
        '--dir-in',
        help='Diretório de entrada com os arquivos em inglês (ex: ./en)'
    )
    manual.add_argument(
        '--dir-out',
        help='Diretório de saída para os arquivos traduzidos (ex: ./br)'
    )

    # Grupo 2: Modo auto-detecção
    auto = parser.add_argument_group('modo auto-detecção')
    auto.add_argument(
        '--find',
        metavar='PATH',
        help='Busca recursivamente por diretórios de localização a partir deste caminho'
    )
    auto.add_argument(
        '--auto-translate',
        action='store_true',
        help='Após encontrar, traduz automaticamente sem confirmação (requer --dir-out)'
    )
    auto.add_argument(
        '--max-depth',
        type=int,
        default=5,
        help='Profundidade máxima para busca recursiva (padrão: 5)'
    )

    # Grupo 3: Modo validação
    validate_group = parser.add_argument_group('modo validação')
    validate_group.add_argument(
        '--validate',
        action='store_true',
        help='Apenas valida tradução existente (compara EN vs BR), não traduz'
    )

    # Opções gerais
    parser.add_argument(
        '--delay',
        type=float,
        default=DEFAULT_DELAY,
        help=f'Delay em segundos entre chamadas ao tradutor (padrão: {DEFAULT_DELAY})'
    )

    return parser.parse_args()


def main():
    args = parse_args()

    # Modo validação: só valida e sai
    if args.validate:
        if not args.dir_in or not args.dir_out:
            print("❌ ERRO: --validate requer --dir-in e --dir-out")
            sys.exit(1)

        src_dir = os.path.abspath(os.path.expanduser(args.dir_in))
        dst_dir = os.path.abspath(os.path.expanduser(args.dir_out))

        if not os.path.isdir(src_dir):
            print(f"❌ ERRO: Diretório EN não encontrado: {src_dir}")
            sys.exit(1)
        if not os.path.isdir(dst_dir):
            print(f"❌ ERRO: Diretório BR não encontrado: {dst_dir}")
            sys.exit(1)

        stats, issues = validate_translation(src_dir, dst_dir)
        sys.exit(0)

    # Validar argumentos
    if args.find:
        # Modo auto-detecção
        if not os.path.isdir(args.find):
            print(f"❌ ERRO: Caminho não encontrado: {args.find}")
            sys.exit(1)

        candidates = find_lang_dirs(args.find, max_depth=args.max_depth)

        if not candidates:
            print("❌ Nenhum diretório de localização encontrado.")
            print("\nDica: Procure por diretórios que contenham arquivos .php com $msg_arr")
            sys.exit(1)

        # Filtrar apenas diretórios com idioma 'en'
        en_candidates = [c for c in candidates if detect_language_from_path(c['path']) == 'en']

        if en_candidates:
            print(f"✅ Encontrados {len(en_candidates)} diretórios em inglês (EN)")
            candidates = en_candidates
        else:
            print("⚠️  Nenhum diretório 'en' detectado automaticamente. Mostrando todos.")

        if args.auto_translate:
            if not args.dir_out:
                print("❌ ERRO: --auto-translate requer --dir-out")
                sys.exit(1)
            if len(candidates) != 1:
                print(f"❌ ERRO: --auto-translate requer exatamente 1 candidato, mas foram encontrados {len(candidates)}")
                print("   Use o modo interativo (sem --auto-translate) ou especifique melhor o --find")
                sys.exit(1)
            src_dir = candidates[0]['path']
            dst_dir = os.path.abspath(os.path.expanduser(args.dir_out))
        else:
            # Modo interativo
            src_dir = interactive_select_dir(candidates)
            if not src_dir:
                print("❌ Operação cancelada.")
                sys.exit(0)

            # Sugerir diretório de saída
            suggested_out = suggest_output_dir(src_dir)
            print(f"\n📁 Diretório de entrada selecionado: {src_dir}")
            print(f"📁 Sugestão de saída: {suggested_out}")

            if args.dir_out:
                dst_dir = os.path.abspath(os.path.expanduser(args.dir_out))
                print(f"📁 Usando saída especificada: {dst_dir}")
            else:
                use_suggested = input(f"\nUsar diretório sugerido? [S/n]: ").strip().lower()
                if use_suggested in ['n', 'no', 'nao', 'não']:
                    custom_out = input("Digite o caminho do diretório de saída: ").strip()
                    dst_dir = os.path.abspath(os.path.expanduser(custom_out))
                else:
                    dst_dir = suggested_out

    elif args.dir_in and args.dir_out:
        # Modo manual
        src_dir = os.path.abspath(os.path.expanduser(args.dir_in))
        dst_dir = os.path.abspath(os.path.expanduser(args.dir_out))

        if not os.path.isdir(src_dir):
            print(f"❌ ERRO: Diretório de entrada não encontrado: {src_dir}")
            sys.exit(1)
    else:
        print("❌ ERRO: Use --find para auto-detecção ou --dir-in + --dir-out para modo manual")
        print("   Execute com --help para ver exemplos")
        sys.exit(1)

    # Garantir que translate-shell está instalado
    ensure_trans()

    print("\n" + "="*60)
    print(f"Origem:  {src_dir}")
    print(f"Destino: {dst_dir}")
    print(f"Idioma:  {SOURCE_LANG} → {TARGET_LANG}")
    print(f"Delay:   {args.delay}s entre chamadas")
    print("="*60 + "\n")

    # Confirmar antes de iniciar (a menos que --auto-translate)
    if not args.auto_translate:
        confirm = input("Iniciar tradução? [S/n]: ").strip().lower()
        if confirm in ['n', 'no', 'nao', 'não']:
            print("❌ Operação cancelada.")
            sys.exit(0)

    file_count = 0

    for dirpath, dirnames, filenames in os.walk(src_dir):
        dirnames.sort()
        for filename in sorted(filenames):
            if not filename.endswith('.php'):
                continue

            src_path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(src_path, src_dir)
            dst_path = os.path.join(dst_dir, rel_path)

            file_count += 1
            print(f"[{file_count}] {rel_path}")
            process_file(src_path, dst_path, dst_dir, args.delay)
            print()

    print(f"✅ Completo. {file_count} arquivos processados.")

    # Validar automaticamente após tradução
    print("\n" + "="*60)
    print("🔍 Iniciando validação automática...")
    print("="*60)

    stats, issues = validate_translation(src_dir, dst_dir)


if __name__ == '__main__':
    main()
