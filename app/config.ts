/** En ligne (Firebase), l'interface parle à l'API qui tourne sur ton PC. En local (npm run console), le proxy Vite suffit. */
export const API_BASE: string = import.meta.env.VITE_API_BASE ?? "";
export const ONLINE = API_BASE !== "";
