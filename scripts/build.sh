#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=${ROOT_DIR:-/workspace}
WORK_DIR=${WORK_DIR:-/work}
PROFILE=${PROFILE:-ax9000}
CLEAN=${CLEAN:-0}
JOBS=${JOBS:-0}
PREPARE_ONLY=${PREPARE_ONLY:-0}

PROFILE_DIR="$ROOT_DIR/profiles/$PROFILE"
if [ ! -f "$PROFILE_DIR/profile.env" ]; then
  echo "Unknown profile: $PROFILE" >&2
  exit 1
fi

source "$PROFILE_DIR/profile.env"

REPO_URL=${OPENWRT_REPO:-https://github.com/openwrt/openwrt.git}
REPO_BRANCH=${REPO_BRANCH:-openwrt-25.12}
OPENWRT_DIR="$WORK_DIR/openwrt-$PROFILE"
OUTPUT_DIR="$ROOT_DIR/outputs/$PROFILE"
REQUESTED_PACKAGES_FILE="$OPENWRT_DIR/.requested-packages"
REQUESTED_DISABLED_PACKAGES_FILE="$OPENWRT_DIR/.requested-disabled-packages"
REQUESTED_CONFIG_FILE="$OPENWRT_DIR/.requested-build.config"

mkdir -p "$WORK_DIR" "$OUTPUT_DIR"

clone_or_update_source() {
  local current_url=""

  if [ -d "$OPENWRT_DIR/.git" ]; then
    current_url="$(git -C "$OPENWRT_DIR" remote get-url origin 2>/dev/null || true)"
    if [ "$current_url" != "$REPO_URL" ]; then
      echo "Source repository changed; replacing cached checkout"
      rm -rf "$OPENWRT_DIR"
    fi
  fi

  if [ ! -d "$OPENWRT_DIR/.git" ]; then
    git clone --depth 1 --branch "$REPO_BRANCH" "$REPO_URL" "$OPENWRT_DIR"
    return
  fi

  git -C "$OPENWRT_DIR" fetch --depth 1 origin "$REPO_BRANCH"
  git -C "$OPENWRT_DIR" checkout -B "$REPO_BRANCH" "origin/$REPO_BRANCH"
  git -C "$OPENWRT_DIR" reset --hard "origin/$REPO_BRANCH"
  git -C "$OPENWRT_DIR" clean -ffdx \
    -e feeds/ -e dl/ -e build_dir/ -e staging_dir/
}

reset_preserved_feeds() {
  local feeds_dir="$1"
  [ -d "$feeds_dir" ] || return 0

  while IFS= read -r -d '' feed_dir; do
    [ -e "$feed_dir/.git" ] || continue
    git -C "$feed_dir" reset --hard
    git -C "$feed_dir" clean -ffdx
  done < <(find "$feeds_dir" -mindepth 1 -maxdepth 1 -type d -print0)
}

apply_feed_options() {
  local options_file="${BUILD_OPTIONS_FILE:-$PROFILE_DIR/feeds.json}"
  [ -f "$options_file" ] || {
    echo "BUILD_OPTIONS_FILE not found: $options_file" >&2
    exit 1
  }

  python3 "$ROOT_DIR/scripts/build_config.py" feeds \
    "$options_file" --source "$PWD"
}

apply_build_options() {
  local options_file="${BUILD_OPTIONS_FILE:-}"
  if [ -z "$options_file" ]; then
    options_file="$PROFILE_DIR/default-options.json"
  fi
  [ -f "$options_file" ] || {
    echo "BUILD_OPTIONS_FILE not found: $options_file" >&2
    exit 1
  }

  python3 "$ROOT_DIR/scripts/build_config.py" options "$options_file" \
    --source "$PWD" --profile-dir "$PROFILE_DIR"
  cat .build-options.config >> .config
}

apply_branding_options() {
  local options_file="${BUILD_OPTIONS_FILE:-$PROFILE_DIR/default-options.json}"
  python3 "$ROOT_DIR/scripts/build_config.py" branding "$options_file" \
    --source "$PWD" --profile-dir "$PROFILE_DIR"
}

feed_index_has_package() {
  local index_file="$1"
  local package="$2"
  awk -v package="$package" '
    $1 == "Package:" && $2 == package { found = 1; exit }
    END { exit(found ? 0 : 1) }
  ' "$index_file"
}

install_feeds() {
  local attempt
  local full_feed
  local index_file
  local feed
  local package
  local -a full_feeds=(packages luci routing telephony video nss_packages sqm_scripts_nss)

  for attempt in 1 2 3; do
    if ./scripts/feeds update -a; then
      break
    fi
    if [ "$attempt" -eq 3 ]; then
      echo "Feed update failed after $attempt attempts" >&2
      return 1
    fi
    echo "Feed update failed; retrying in $((attempt * 5)) seconds" >&2
    sleep $((attempt * 5))
  done

  for full_feed in "${full_feeds[@]}"; do
    if [ -f "feeds/$full_feed.index" ]; then
      ./scripts/feeds install -a -p "$full_feed"
    fi
  done

  for index_file in feeds/*.index; do
    [ -f "$index_file" ] || continue
    feed="$(basename "$index_file" .index)"
    if [[ " ${full_feeds[*]} " == *" $feed "* ]]; then
      continue
    fi

    while IFS= read -r package; do
      if feed_index_has_package "$index_file" "$package"; then
        ./scripts/feeds install -p "$feed" "$package"
      fi
    done < "$REQUESTED_PACKAGES_FILE"
  done
}

verify_final_config() {
  local package
  local missing=0
  local -a devices=()

  while IFS= read -r package; do
    if ! grep -Fqx "CONFIG_PACKAGE_${package}=y" .config && \
       ! grep -Fqx "CONFIG_PACKAGE_${package}=m" .config; then
      echo "Requested package was not enabled: $package" >&2
      missing=1
    fi
  done < "$REQUESTED_PACKAGES_FILE"

  while IFS= read -r package; do
    if grep -Fqx "CONFIG_PACKAGE_${package}=y" .config || \
       grep -Fqx "CONFIG_PACKAGE_${package}=m" .config; then
      echo "Package enabled by a selected dependency: $package"
    fi
  done < "$REQUESTED_DISABLED_PACKAGES_FILE"

  mapfile -t devices < <(
    sed -n 's/^CONFIG_TARGET_DEVICE_.*_DEVICE_\(.*\)=y$/\1/p' .config
  )
  if [ "${#devices[@]}" -ne 1 ] || [ "${devices[0]:-}" != "$DEVICE_ID" ]; then
    echo "Expected only device $DEVICE_ID, got: ${devices[*]:-none}" >&2
    missing=1
  fi

  if grep -Fqx "CONFIG_IPV6=y" "$REQUESTED_CONFIG_FILE"; then
    grep -Fqx "CONFIG_IPV6=y" .config || {
      echo "Requested kernel IPv6 support is not enabled" >&2
      missing=1
    }
  elif grep -Fqx "CONFIG_IPV6=y" .config; then
    echo "Kernel IPv6 support was enabled unexpectedly" >&2
    missing=1
  fi

  grep -Fqx "CONFIG_ATH11K_NSS_SUPPORT=y" .config || {
    echo "ATH11K NSS offload is not enabled" >&2
    missing=1
  }

  [ "$missing" -eq 0 ]
}

if [ "$CLEAN" = "1" ]; then
  rm -rf "$OPENWRT_DIR"
fi

clone_or_update_source
reset_preserved_feeds "$OPENWRT_DIR/feeds"
cd "$OPENWRT_DIR"

python3 "$ROOT_DIR/scripts/install_external_packages.py" \
  "$PROFILE_DIR/external-packages.json" --source "$PWD"

if [ -d "$ROOT_DIR/packages" ]; then
  mkdir -p package/openwrt-local
  cp -rf "$ROOT_DIR/packages/." package/openwrt-local/
fi

apply_feed_options

cp -f "$PROFILE_DIR/seed.config" .config

if [ -d "$PROFILE_DIR/files" ]; then
  mkdir -p files
  cp -rf "$PROFILE_DIR/files/." files/
fi

apply_build_options
cp -f .config "$REQUESTED_CONFIG_FILE"

awk -F= '
  /^CONFIG_PACKAGE_.*=(y|m)$/ {
    name = $1
    sub(/^CONFIG_PACKAGE_/, "", name)
    print name
  }
' .config | sort -u > "$REQUESTED_PACKAGES_FILE"

sed -n 's/^# CONFIG_PACKAGE_\(.*\) is not set$/\1/p' .config | \
  sort -u > "$REQUESTED_DISABLED_PACKAGES_FILE"

install_feeds
python3 "$ROOT_DIR/scripts/patch_feed_packages.py" --source "$PWD"
cp -f "$REQUESTED_CONFIG_FILE" .config
apply_branding_options

if [ -f "$PROFILE_DIR/post-patch.sh" ]; then
  /bin/bash "$PROFILE_DIR/post-patch.sh"
fi

make defconfig
verify_final_config

if [ "$PREPARE_ONLY" = "1" ]; then
  rm -rf "$OUTPUT_DIR"
  mkdir -p "$OUTPUT_DIR"
  cp -f .config "$OUTPUT_DIR/${PROFILE}.config"
  echo "Source preparation complete: $OPENWRT_DIR"
  exit 0
fi

# The buildroot does not reliably invalidate base-files when only files/
# changes, so refresh it on every real build to avoid stale first-boot files.
make package/base-files/clean

if [ "$JOBS" -le 0 ]; then
  JOBS="$(($(nproc) + 1))"
fi

make -j"$JOBS" || make V=s

rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"
cp -rf bin/targets/*/*/* "$OUTPUT_DIR"/
cp -f .config "$OUTPUT_DIR/${PROFILE}.config"

echo "Build output: $OUTPUT_DIR"
