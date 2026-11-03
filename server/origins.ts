import type { NextFunction, Request, Response } from "express";

/** Seuls ces sites peuvent parler à l'API locale : la Console en ligne (Firebase) et la Console locale. */
export const ALLOWED_ORIGINS = new Set([
  "https://bureau-des-faits.web.app",
  "https://bureau-des-faits.firebaseapp.com",
  "http://127.0.0.1:5180",
  "http://localhost:5180",
]);

/**
 * CORS restreint + accès au réseau privé (Chrome) + en-tête obligatoire sur les actions.
 * L'en-tête `x-console` force un pré-contrôle CORS : un autre site ne peut pas déclencher d'action en douce.
 */
export const guard = (req: Request, res: Response, next: NextFunction) => {
  const origin = req.headers.origin;
  if (origin) {
    if (!ALLOWED_ORIGINS.has(origin)) {
      res.status(403).json({ error: "origine refusée" });
      return;
    }
    res.set({
      "access-control-allow-origin": origin,
      vary: "Origin",
      "access-control-allow-methods": "GET,POST,PATCH,OPTIONS",
      "access-control-allow-headers": "content-type,x-console",
    });
    if (req.headers["access-control-request-private-network"]) res.set("access-control-allow-private-network", "true");
    if (req.method === "OPTIONS") {
      res.status(204).end();
      return;
    }
  }
  if ((req.method === "POST" || req.method === "PATCH") && req.headers["x-console"] !== "1") {
    res.status(403).json({ error: "action refusée (en-tête x-console manquant)" });
    return;
  }
  next();
};
