#!/usr/bin/env bash
# Deploy the statusline script to the marketplace path that user-level
# settings.json points at.
# Runs locally and on each remote in REMOTES.

set -euo pipefail

function die {
    # args
    local msg="${1:-deploy-statusline failed}"
    # result
    echo "deploy-statusline: $msg" 1>&2
    exit 1
} 1>&2

# --- config ------------------------------------------------------------------

REMOTES=("${STATUSLINE_REMOTES:-hetz}")  # space-separated env override

MARKETPLACE_REL=".claude/plugins/marketplaces/oh-my-claude-plugins/meta/utils/statusline"

# --- locate source -----------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$(cd "$SCRIPT_DIR/../meta/utils/statusline" && pwd)" \
    || die "cannot resolve source dir from $SCRIPT_DIR"
SRC_SCRIPT="$SRC_DIR/omcc-statusline.py"
[ -f "$SRC_SCRIPT" ] || die "missing source: $SRC_SCRIPT"

# Files for marketplace path (script + supporting assets).
MARKETPLACE_FILES=(
    "$SRC_SCRIPT"
    "$SRC_DIR/README.md"
    "$SRC_DIR/config.example.json"
    "$SRC_DIR/demo.png"
    "$SRC_DIR/demo1.png"
    "$SRC_DIR/editor.png"
)

# --- local deploy ------------------------------------------------------------

function deploy_local {
    # vars
    local mp="$HOME/$MARKETPLACE_REL"
    # code
    install -d -m 755 "$mp"
    cp -f "${MARKETPLACE_FILES[@]}" "$mp/"
    echo "local marketplace: ok ($mp)"
}

# --- remote deploy -----------------------------------------------------------

function deploy_remote {
    # args
    local host="$1"
    # code
    ssh -o ConnectTimeout=10 "$host" "install -d -m 755 \$HOME/$MARKETPLACE_REL" \
        || die "$host: cannot create marketplace path"
    scp -q -o ConnectTimeout=10 "${MARKETPLACE_FILES[@]}" "$host:$MARKETPLACE_REL/" \
        || die "$host: marketplace copy failed"
    echo "$host marketplace:   ok"
}

# --- verify ------------------------------------------------------------------

function verify {
    # vars
    local expected
    local actual
    local host
    # code
    expected=$(sha256sum "$SRC_SCRIPT" | awk '{print $1}')
    actual=$(sha256sum "$HOME/$MARKETPLACE_REL/omcc-statusline.py" | awk '{print $1}')
    [ "$expected" = "$actual" ] || die "local marketplace sha mismatch"

    for host in "${REMOTES[@]}"; do
        actual=$(ssh -o ConnectTimeout=10 "$host" \
            "sha256sum \$HOME/$MARKETPLACE_REL/omcc-statusline.py | awk '{print \$1}'") \
            || die "$host: sha probe failed"
        [ "$expected" = "$actual" ] || die "$host marketplace sha mismatch"
    done

    echo "verify: all paths match $expected"
}

# --- main --------------------------------------------------------------------

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    cat <<EOF
deploy-statusline.sh — deploy omcc-statusline.py to the marketplace path.

Target per host:
  - \$HOME/$MARKETPLACE_REL

Remotes: ${REMOTES[*]}  (override with STATUSLINE_REMOTES="host1 host2")

Usage:
  ./scripts/deploy-statusline.sh            # deploy everywhere + verify
  STATUSLINE_REMOTES="" ./scripts/deploy-statusline.sh   # local only
EOF
    exit 0
fi

deploy_local
for host in "${REMOTES[@]}"; do
    [ -z "$host" ] && continue
    deploy_remote "$host"
done
verify
