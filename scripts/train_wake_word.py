#!/usr/bin/env python3
"""Train or download wake word models for smart-home-mind.

Supports two modes:
  1. download — fetch pre-trained English models for quick testing
  2. train     — train a custom wake word from your own recordings

Examples:
    # Quick test with English model
    python scripts/train_wake_word.py download --model hey_jarvis

    # Train custom Chinese wake word
    python scripts/train_wake_word.py train \
        --name nihao_guanjia \
        --positive-dir models/wake-words/nihao_guanjia/positive \
        --negative-dir models/wake-words/nihao_guanjia/negative \
        --output models/nihao_guanjia.onnx
"""
import argparse
import logging
import sys
import urllib.request
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
_LOGGER = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = REPO_ROOT / "models"
PRETRAINED_MODELS = {
    "hey_jarvis": "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/hey_jarvis_v0.1.onnx",
    "alexa": "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/alexa_v0.1.onnx",
    "hey_mycroft": "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/hey_mycroft_v0.1.onnx",
    "hey_rhasspy": "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/hey_rhasspy_v0.1.onnx",
}


def cmd_download(args):
    """Download a pre-trained model from openWakeWord releases."""
    name = args.model
    if name not in PRETRAINED_MODELS:
        _LOGGER.error("Unknown model: %s", name)
        _LOGGER.info("Available: %s", ", ".join(PRETRAINED_MODELS.keys()))
        sys.exit(1)

    url = PRETRAINED_MODELS[name]
    dest = MODELS_DIR / f"{name}.onnx"
    dest.parent.mkdir(parents=True, exist_ok=True)

    _LOGGER.info("Downloading %s -> %s", url, dest)
    urllib.request.urlretrieve(url, dest)
    _LOGGER.info("Done. You can now set WAKE_WORD_MODEL=%s in docker-compose.yml", dest)


def cmd_train(args):
    """Train a custom wake word classifier."""
    try:
        import torch
        import torch.nn as nn
        import torchaudio
        import numpy as np
        import soundfile as sf
        from sklearn.model_selection import train_test_split
    except ImportError as exc:
        _LOGGER.error("Missing dependency: %s", exc)
        _LOGGER.error("Please run: pip install torch torchaudio numpy soundfile scikit-learn")
        sys.exit(1)

    positive_dir = Path(args.positive_dir)
    negative_dir = Path(args.negative_dir)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not positive_dir.exists() or not any(positive_dir.glob("*.wav")):
        _LOGGER.error("No WAV files found in %s", positive_dir)
        _LOGGER.error(
            "Please record 20-50 clips of your wake word (1-3 seconds each),\n"
            "16 kHz, mono, 16-bit PCM, and place them in that directory."
        )
        sys.exit(1)

    # ------------------------------------------------------------------
    # Hyper-parameters
    # ------------------------------------------------------------------
    SAMPLE_RATE = 16000
    WINDOW_SEC = 1.5
    WINDOW_SAMPLES = int(SAMPLE_RATE * WINDOW_SEC)
    BATCH_SIZE = 32
    EPOCHS = args.epochs
    LR = args.lr
    DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    _LOGGER.info("Training on %s", DEVICE)

    # ------------------------------------------------------------------
    # Model — 1-D CNN on raw audio
    # ------------------------------------------------------------------
    class WakeWordCNN(nn.Module):
        def __init__(self, n_samples: int = WINDOW_SAMPLES):
            super().__init__()
            self.net = nn.Sequential(
                nn.Conv1d(1, 32, kernel_size=80, stride=4),
                nn.BatchNorm1d(32),
                nn.ReLU(),
                nn.MaxPool1d(4),

                nn.Conv1d(32, 64, kernel_size=3, padding=1),
                nn.BatchNorm1d(64),
                nn.ReLU(),
                nn.MaxPool1d(4),

                nn.Conv1d(64, 128, kernel_size=3, padding=1),
                nn.BatchNorm1d(128),
                nn.ReLU(),
                nn.AdaptiveAvgPool1d(1),
            )
            self.classifier = nn.Sequential(
                nn.Linear(128, 64),
                nn.ReLU(),
                nn.Dropout(0.5),
                nn.Linear(64, 1),
                nn.Sigmoid(),
            )

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            # x: [batch, n_samples]
            x = x.unsqueeze(1)                 # [batch, 1, n_samples]
            x = self.net(x).squeeze(-1)        # [batch, 128]
            return self.classifier(x)          # [batch, 1]

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------
    def load_wav(path: Path) -> np.ndarray:
        data, sr = sf.read(str(path), dtype="float32")
        if sr != SAMPLE_RATE:
            _LOGGER.warning("Resampling %s from %d Hz to %d Hz", path, sr, SAMPLE_RATE)
            data = torchaudio.functional.resample(
                torch.from_numpy(data), sr, SAMPLE_RATE
            ).numpy()
        if data.ndim > 1:
            data = data.mean(axis=1)  # stereo -> mono
        return data

    def extract_clips(audio: np.ndarray, label: int):
        """Extract fixed-length windows with overlap."""
        clips, labels = [], []
        step = WINDOW_SAMPLES // 2
        for start in range(0, max(1, len(audio) - WINDOW_SAMPLES + 1), step):
            clip = audio[start : start + WINDOW_SAMPLES]
            if len(clip) < WINDOW_SAMPLES:
                clip = np.pad(clip, (0, WINDOW_SAMPLES - len(clip)))
            clips.append(clip)
            labels.append(label)
        return clips, labels

    def augment(clip: np.ndarray) -> np.ndarray:
        """Random augmentation: time shift, speed change, noise."""
        # Time shift
        shift = np.random.randint(-800, 800)
        if shift > 0:
            clip = np.pad(clip, (shift, 0))[:WINDOW_SAMPLES]
        elif shift < 0:
            clip = np.pad(clip, (0, -shift))[-WINDOW_SAMPLES:]

        # Speed perturbation
        if np.random.rand() < 0.3:
            factor = np.random.uniform(0.9, 1.1)
            clip = torchaudio.functional.resample(
                torch.from_numpy(clip), SAMPLE_RATE, int(SAMPLE_RATE * factor)
            ).numpy()
            if len(clip) > WINDOW_SAMPLES:
                clip = clip[:WINDOW_SAMPLES]
            else:
                clip = np.pad(clip, (0, WINDOW_SAMPLES - len(clip)))

        # Add noise
        if np.random.rand() < 0.3:
            noise = np.random.normal(0, 0.005, clip.shape)
            clip = clip + noise

        return np.clip(clip, -1.0, 1.0).astype(np.float32)

    _LOGGER.info("Loading positive samples from %s", positive_dir)
    pos_clips, pos_labels = [], []
    for wav in sorted(positive_dir.glob("*.wav")):
        audio = load_wav(wav)
        clips, labels = extract_clips(audio, label=1)
        pos_clips.extend(clips)
        pos_labels.extend(labels)
        # Augment each clip 3x
        for _ in range(3):
            pos_clips.extend([augment(c) for c in clips])
            pos_labels.extend(labels)
    _LOGGER.info("Positive clips: %d", len(pos_clips))

    neg_clips, neg_labels = [], []
    if negative_dir.exists():
        _LOGGER.info("Loading negative samples from %s", negative_dir)
        for wav in sorted(negative_dir.glob("*.wav")):
            audio = load_wav(wav)
            clips, labels = extract_clips(audio, label=0)
            neg_clips.extend(clips)
            neg_labels.extend(labels)
    _LOGGER.info("Negative clips: %d", len(neg_clips))

    if len(neg_clips) < len(pos_clips):
        _LOGGER.warning(
            "Too few negative samples (%d < %d). "
            "Add more non-wake-word audio to reduce false triggers.",
            len(neg_clips), len(pos_clips),
        )

    all_clips = pos_clips + neg_clips
    all_labels = pos_labels + neg_labels

    X_train, X_val, y_train, y_val = train_test_split(
        all_clips, all_labels, test_size=0.2, random_state=42, stratify=all_labels
    )

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------
    model = WakeWordCNN(WINDOW_SAMPLES).to(DEVICE)
    criterion = nn.BCELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=LR)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5)

    def make_loader(X, y, shuffle=True):
        tensor_x = torch.tensor(np.stack(X), dtype=torch.float32)
        tensor_y = torch.tensor(np.array(y, dtype=np.float32)).unsqueeze(1)
        dataset = torch.utils.data.TensorDataset(tensor_x, tensor_y)
        return torch.utils.data.DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=shuffle)

    train_loader = make_loader(X_train, y_train)
    val_loader = make_loader(X_val, y_val, shuffle=False)

    best_val_loss = float("inf")
    best_state = None

    for epoch in range(1, EPOCHS + 1):
        model.train()
        train_loss = 0.0
        for xb, yb in train_loader:
            xb, yb = xb.to(DEVICE), yb.to(DEVICE)
            optimizer.zero_grad()
            pred = model(xb)
            loss = criterion(pred, yb)
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * len(xb)

        train_loss /= len(train_loader.dataset)

        model.eval()
        val_loss = 0.0
        correct = 0
        with torch.no_grad():
            for xb, yb in val_loader:
                xb, yb = xb.to(DEVICE), yb.to(DEVICE)
                pred = model(xb)
                val_loss += criterion(pred, yb).item() * len(xb)
                correct += ((pred > 0.5).float() == yb).sum().item()

        val_loss /= len(val_loader.dataset)
        val_acc = correct / len(val_loader.dataset)
        scheduler.step(val_loss)

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state = model.state_dict().copy()

        _LOGGER.info(
            "Epoch %02d | train_loss=%.4f | val_loss=%.4f | val_acc=%.2f%%",
            epoch, train_loss, val_loss, val_acc * 100,
        )

    # ------------------------------------------------------------------
    # Export to ONNX
    # ------------------------------------------------------------------
    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval().cpu()

    dummy_input = torch.randn(1, WINDOW_SAMPLES)
    torch.onnx.export(
        model,
        dummy_input,
        str(output_path),
        input_names=["audio"],
        output_names=["score"],
        dynamic_axes={"audio": {0: "batch"}, "score": {0: "batch"}},
        opset_version=11,
    )
    _LOGGER.info("Exported ONNX model: %s", output_path)
    _LOGGER.info(
        "Update docker-compose.yml with:\n"
        "  WAKE_WORD_MODEL=/models/%s\n"
        "  WAKE_WORD_THRESHOLD=0.7",
        output_path.name,
    )


def main():
    parser = argparse.ArgumentParser(description="Wake word model manager")
    sub = parser.add_subparsers(dest="command", required=True)

    p_down = sub.add_parser("download", help="Download a pre-trained model")
    p_down.add_argument("--model", required=True, choices=list(PRETRAINED_MODELS.keys()))

    p_train = sub.add_parser("train", help="Train a custom wake word")
    p_train.add_argument("--name", required=True, help="Wake word name (e.g. nihao_guanjia)")
    p_train.add_argument("--positive-dir", required=True, help="Directory with positive WAV samples")
    p_train.add_argument("--negative-dir", default="", help="Directory with negative WAV samples")
    p_train.add_argument("--output", required=True, help="Output ONNX path")
    p_train.add_argument("--epochs", type=int, default=30)
    p_train.add_argument("--lr", type=float, default=1e-3)

    args = parser.parse_args()
    if args.command == "download":
        cmd_download(args)
    elif args.command == "train":
        cmd_train(args)


if __name__ == "__main__":
    main()
