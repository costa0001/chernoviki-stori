#!/bin/bash
# Подготовка рабочей среды в НОВОМ чате (контейнер каждый раз чистый).
# Запуск: bash setup.sh      (≈2–4 мин; модели качаются с GitHub Releases, это разрешённый адрес)
set -e
mkdir -p /home/claude/asr && cd /home/claude/asr
python3 -c "import onnxruntime, numpy, PIL" 2>/dev/null || pip install onnxruntime numpy pillow --break-system-packages -q
B=https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models
[ -d sherpa-onnx-whisper-small ] || (curl -sSL -o s.tar.bz2 $B/sherpa-onnx-whisper-small.tar.bz2 && tar xjf s.tar.bz2 && rm s.tar.bz2)
# medium нужен только для спорных мест (≈1 ГБ). Раскомментировать при необходимости:
# [ -d sherpa-onnx-whisper-medium ] || (curl -sSL -o m.tar.bz2 $B/sherpa-onnx-whisper-medium.tar.bz2 && tar xjf m.tar.bz2 && rm m.tar.bz2)
ls /usr/share/fonts/opentype/inter/Inter-ExtraBold.otf >/dev/null || echo "ВНИМАНИЕ: нет шрифта Inter (apt-get install fonts-inter)"
ls /usr/share/fonts/truetype/dejavu/DejaVuSerifCondensed-Bold.ttf >/dev/null || echo "ВНИМАНИЕ: нет DejaVu"
cd "$(dirname "$0")" 2>/dev/null; python3 make_top.py
echo "OK: среда готова. Ядер: $(nproc), память: $(free -g | awk '/Mem/{print $2}') ГБ"
