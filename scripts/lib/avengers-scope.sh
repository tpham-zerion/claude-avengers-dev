#!/bin/bash
# Avengers Dev - workspace scope resolver (shared by the SessionStart hooks).
#
# Sourced by scripts/session-start.sh and scripts/compact-resume.sh. It lives in
# one file because the two hooks must agree exactly: any drift between them shows
# up as a banner with no persona or, far worse, a persona outside the workspace.
#
#   avengers_scope_state [dir] [roots]
#
# echoes exactly one of:
#   yes      - no scope is configured (the persona applies everywhere), or dir is
#              a configured root or lives underneath one
#   no       - dir resolved, at least one root resolved, and dir is under none
#   unknown  - a scope is configured but could not be measured: dir does not
#              resolve, no configured root resolves, or the scope file exists but
#              cannot be read
#
# dir defaults to CLAUDE_PROJECT_DIR, then $PWD. roots, when given and non-empty,
# is a `:`-separated list used instead of the configuration below.
#
# Configuration (the first source that supplies at least one root wins):
#   1. AVENGERS_SCOPE_ROOTS - a `:`-separated list of absolute paths. An empty
#      value, or one made only of separators, counts as unset.
#   2. ${CLAUDE_CONFIG_DIR:-$HOME/.claude}/avengers-scope - one absolute path per
#      line. Blank lines and lines starting with `#` are ignored, surrounding
#      whitespace is trimmed, and a leading `~` or `~/` expands to $HOME.
# The same trimming and `~` expansion apply to the env list. An entry that is not
# absolute after expansion cannot be resolved and is skipped.
#
# Unconfigured means unscoped: with no root from either source the answer is `yes`
# everywhere, so a user who never sets a scope sees the hooks behave as they did
# before scoping existed.
#
# Callers choose the fail direction for `unknown`, and they are DELIBERATELY
# OPPOSITE: the banner fails open, the persona injection fails closed.
#
# stdin is NEVER read here. The SessionStart payload does carry a `cwd`, but a
# hook that drains stdin can starve anything downstream of it. CLAUDE_PROJECT_DIR
# is set on hook runs, with $PWD matching it, so the env var plus a $PWD fallback
# is sufficient.

# Trim surrounding whitespace and expand a leading `~` / `~/`. `~user` is left as
# is, so it stays relative and is skipped as unresolvable.
_avengers_scope_normalise() {
  local _entry="$1"
  _entry="${_entry#"${_entry%%[![:space:]]*}"}"
  _entry="${_entry%"${_entry##*[![:space:]]}"}"
  case "$_entry" in
    "~")   _entry="${HOME-}" ;;
    "~/"*) _entry="${HOME-}/${_entry#"~/"}" ;;
  esac
  printf '%s' "$_entry"
}

# Print the entries of a `:`-separated list, one per line, skipping empty ones.
_avengers_scope_split() {
  local _rest="$1:" _entry
  while [ -n "$_rest" ]; do
    _entry="$(_avengers_scope_normalise "${_rest%%:*}")"
    _rest="${_rest#*:}"
    [ -n "$_entry" ] && printf '%s\n' "$_entry"
  done
  return 0
}

# Print the configured roots, one per line; print nothing when unconfigured.
# Returns 1 when the scope file exists but cannot be read: a scope was set and we
# could not see it, which is `unknown`, not "unconfigured".
_avengers_scope_roots() {
  local _from_list _file _line
  _from_list="$(_avengers_scope_split "${1:-${AVENGERS_SCOPE_ROOTS-}}")"
  if [ -n "$_from_list" ]; then
    printf '%s\n' "$_from_list"
    return 0
  fi

  if [ -n "${CLAUDE_CONFIG_DIR-}" ]; then
    _file="$CLAUDE_CONFIG_DIR/avengers-scope"
  elif [ -n "${HOME-}" ]; then
    _file="$HOME/.claude/avengers-scope"
  else
    return 0
  fi
  # A dangling symlink fails -e but passes -L; it is configured-but-unreadable.
  if [ ! -e "$_file" ] && [ ! -L "$_file" ]; then
    return 0
  fi
  if [ ! -f "$_file" ] || [ ! -r "$_file" ]; then
    return 1
  fi
  # `|| [ -n ... ]` keeps a last line that has no trailing newline.
  while IFS= read -r _line || [ -n "$_line" ]; do
    _line="$(_avengers_scope_normalise "$_line")"
    case "$_line" in
      ""|"#"*) ;;
      *) printf '%s\n' "$_line" ;;
    esac
  done < "$_file"
  return 0
}

avengers_scope_state() {
  # `${1-...}` (no colon): an explicitly empty dir stays empty and yields
  # `unknown` rather than silently falling back to $PWD. Only an ABSENT argument
  # takes the hook's default of CLAUDE_PROJECT_DIR, then $PWD.
  local _dir="${1-${CLAUDE_PROJECT_DIR:-$PWD}}"
  local _roots _dir_real _root _root_real _resolved=0

  if ! _roots="$(_avengers_scope_roots "${2-}")"; then
    printf 'unknown\n'
    return 0
  fi
  # Unconfigured means unscoped.
  if [ -z "$_roots" ]; then
    printf 'yes\n'
    return 0
  fi

  # `pwd -P` resolves symlinks and strips trailing slashes on BOTH sides, so
  # neither can produce a false negative. A path that cannot be entered is
  # reported as `unknown`, not as out-of-scope: we did not measure it, so we do
  # not get to claim it is outside.
  _dir_real=""
  if [ -n "$_dir" ]; then
    _dir_real="$(cd "$_dir" 2>/dev/null && pwd -P)" || :
  fi
  if [ -z "$_dir_real" ]; then
    printf 'unknown\n'
    return 0
  fi

  # The loop reads the here-document, never the hook's stdin.
  while IFS= read -r _root; do
    # A relative entry would resolve against whatever the hook's cwd happens to
    # be, so it is treated as unresolvable.
    case "$_root" in /*) ;; *) continue ;; esac
    _root_real="$(cd "$_root" 2>/dev/null && pwd -P)" || continue
    [ -n "$_root_real" ] || continue
    _resolved=1
    # The trailing slash on the candidate lets the root itself match "$root"/*,
    # while keeping a sibling such as <root>-other out. ${_root_real%/} keeps `/`
    # as a root from becoming `//*`. The root is quoted so a glob character in
    # the path stays literal.
    case "$_dir_real/" in
      "${_root_real%/}"/*) printf 'yes\n'; return 0 ;;
    esac
  done <<EOF
$_roots
EOF

  # Some root was measured and dir is under none of them: `no`. If no root could
  # be measured at all, we cannot claim dir is outside: `unknown`.
  if [ "$_resolved" = 1 ]; then
    printf 'no\n'
  else
    printf 'unknown\n'
  fi
}
