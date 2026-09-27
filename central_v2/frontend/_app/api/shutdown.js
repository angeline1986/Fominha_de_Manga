export async function shutdownServer() {
  const response = await fetch("/api/shutdown", { method: "POST" });

  if (!response.ok) {
    throw new Error(`Falha ao finalizar servidor (${response.status}).`);
  }

  const result = await response.json();
  if (result.status !== "shutting_down") {
    throw new Error("O servidor não confirmou o encerramento.");
  }
}
