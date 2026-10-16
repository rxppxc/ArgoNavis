const GB = 1_073_741_824;
const MB = 1_048_576;
const KB = 1_024;

export function formatBytes(bytes: number): string {
  if (bytes >= GB) return (bytes / GB).toFixed(2) + " GB";
  if (bytes >= MB) return (bytes / MB).toFixed(2) + " MB";
  if (bytes >= KB) return (bytes / KB).toFixed(2) + " KB";
  return bytes + " B";
}
