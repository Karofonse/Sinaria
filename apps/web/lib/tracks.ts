import { api } from "@/lib/api";

/** Pide una URL firmada de corta duración y dispara la descarga del archivo en el navegador. */
export async function downloadTrack(trackId: string, suggestedName: string): Promise<void> {
  const { url } = await api<{ url: string }>(`/v1/tracks/${trackId}/download-url`);
  const a = document.createElement("a");
  a.href = url;
  a.download = suggestedName;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
}
