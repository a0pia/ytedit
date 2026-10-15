#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cache_root="${HYPE_SETUP_CACHE:-/workspace/.cache/hype-studio}"
local_tts_root="${LOCAL_TTS_ROOT:-/workspace/.tools/espeak}"
mkdir -p "$cache_root/npm" "$cache_root/pip" "$cache_root/electron"
export npm_config_cache="$cache_root/npm"
export PIP_CACHE_DIR="$cache_root/pip"
export electron_config_cache="$cache_root/electron"

# Install Debian packages into the workspace without sudo or maintainer scripts.
# APT verifies the repository signature and package hashes using Debian's keyring.
if [[ "$(uname -s)" == 'Linux' ]] && ! command -v espeak-ng >/dev/null 2>&1 && ! command -v espeak >/dev/null 2>&1 && [[ ! -x "$local_tts_root/usr/bin/espeak-ng" ]]; then
  if ! command -v apt-get >/dev/null 2>&1 || ! command -v dpkg-deb >/dev/null 2>&1 || [[ ! -r /usr/share/keyrings/debian-archive-keyring.gpg ]]; then
    echo 'Bu bulut kurulumunda Debian APT, dpkg-deb ve Debian arşiv anahtarlığı gerekiyor.'
    exit 1
  fi
  if [[ "$(dpkg --print-architecture)" != 'amd64' ]]; then
    echo 'Çalışma alanına eSpeak kurulumu bu sürümde yalnızca Debian amd64 için destekleniyor.'
    exit 1
  fi
  distribution_name="$(. /etc/os-release; echo "${ID:-}")"
  distribution_codename="$(. /etc/os-release; echo "${VERSION_CODENAME:-}")"
  if [[ "$distribution_name" != 'debian' || "$distribution_codename" != 'trixie' ]]; then
    echo 'Çalışma alanına eSpeak kurulumu Debian trixie içindir. Sisteminize uygun espeak-ng kurulumunu kullanın.'
    exit 1
  fi
  apt_root="$local_tts_root/apt"
  mkdir -p "$apt_root/empty" "$apt_root/lists/partial" "$apt_root/archives/partial" "$local_tts_root/packages"
  cat > "$apt_root/sources.list" <<'APT_SOURCES'
deb [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://deb.debian.org/debian trixie main
APT_SOURCES
  cat > "$apt_root/apt.conf" <<APT_CONFIG
Dir::Etc::parts "$apt_root/empty";
Dir::Etc::main "$apt_root/unused";
Dir::Etc::sourcelist "$apt_root/sources.list";
Dir::Etc::sourceparts "$apt_root/empty";
Dir::State::lists "$apt_root/lists";
Dir::Cache::archives "$apt_root/archives";
Dir::State::status "/var/lib/dpkg/status";
APT::Sandbox::User "$(id -un)";
Acquire::Languages "none";
APT_CONFIG
  APT_CONFIG="$apt_root/apt.conf" apt-get update
  (
    cd "$local_tts_root/packages"
    APT_CONFIG="$apt_root/apt.conf" apt-get download espeak-ng espeak-ng-data libespeak-ng1 libpcaudio0 libsonic0
    for package_file in ./*.deb; do
      dpkg-deb -x "$package_file" "$local_tts_root"
    done
  )
fi

cd "$project_dir"
bash scripts/setup.sh
echo 'Bulut ortamı hazır. Web sunucusu: npm run dev'
