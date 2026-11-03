/** En ligne (Firebase), l'interface parle à l'API qui tourne sur ton PC. En local (npm run console), le proxy Vite suffit. */
export const API_BASE: string = import.meta.env.VITE_API_BASE ?? "";
export const ONLINE = API_BASE !== "";

/** Console publiée sur le cloud : aucun appel vers le PC (pas besoin de lancer npm run api). */
export const CLOUD_ONLY: boolean = (import.meta.env.VITE_CLOUD_REPO ?? "") !== "";
