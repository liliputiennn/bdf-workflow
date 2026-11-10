import { registerRoot } from "remotion";
import { FormatsRoot } from "./index";

// Entrée dédiée aux formats maison : n'embarque que src/formats (le bundle complet dépend d'épisodes absents du dépôt cloud).
registerRoot(FormatsRoot);
