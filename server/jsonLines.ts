/**
 * Lecture JSON qui retient la ligne de chaque valeur, pour expliquer une erreur « ligne 42 : … ».
 * Accepte une réponse de Claude entourée de texte ou d'un bloc ```json.
 */

export type Path = (string | number)[];
export type Parsed = { value: unknown; lineOf: (path: Path) => number | undefined };

export class JsonLineError extends Error {
  constructor(
    message: string,
    public line: number,
  ) {
    super(`ligne ${line} : ${message}`);
  }
}

/** Retire le texte autour du JSON (bloc ```json … ``` ou premier « { » jusqu'au dernier « } »). */
export const extractJson = (text: string): { json: string; offsetLines: number } => {
  const fence = /```(?:json)?\s*\n([\s\S]*?)```/.exec(text);
  if (fence) return { json: fence[1], offsetLines: text.slice(0, fence.index).split("\n").length };
  const a = text.indexOf("{");
  const b = text.lastIndexOf("}");
  if (a < 0 || b < a) return { json: text, offsetLines: 0 };
  return { json: text.slice(a, b + 1), offsetLines: text.slice(0, a).split("\n").length - 1 };
};

export const parseWithLines = (input: string): Parsed => {
  const { json: s, offsetLines } = extractJson(input);
  const lines = new Map<string, number>();
  let i = 0;
  let line = 1 + offsetLines;
  const fail = (msg: string): never => {
    throw new JsonLineError(msg, line);
  };
  const ws = () => {
    while (i < s.length && /\s/.test(s[i])) {
      if (s[i] === "\n") line++;
      i++;
    }
  };
  const str = (): string => {
    let out = "";
    i++;
    while (i < s.length && s[i] !== '"') {
      if (s[i] === "\n") fail("guillemet fermant manquant dans un texte");
      if (s[i] === "\\") {
        const n = s[i + 1];
        const map: Record<string, string> = { n: "\n", t: "\t", r: "\r", b: "\b", f: "\f", '"': '"', "\\": "\\", "/": "/" };
        if (n === "u") {
          out += String.fromCharCode(parseInt(s.slice(i + 2, i + 6), 16));
          i += 6;
          continue;
        }
        if (!(n in map)) fail(`caractère d'échappement inconnu « \\${n} »`);
        out += map[n];
        i += 2;
        continue;
      }
      out += s[i++];
    }
    if (i >= s.length) fail("texte non fermé (guillemet manquant)");
    i++;
    return out;
  };
  const val = (path: Path): unknown => {
    ws();
    lines.set(JSON.stringify(path), line);
    const c = s[i];
    if (c === "{") {
      i++;
      const o: Record<string, unknown> = {};
      ws();
      if (s[i] === "}") return i++, o;
      for (;;) {
        ws();
        if (s[i] !== '"') fail(s[i] === "}" ? "virgule en trop avant « } »" : "nom de champ attendu entre guillemets");
        const k = str();
        ws();
        if (s[i] !== ":") fail(`« : » attendu après « ${k} »`);
        i++;
        o[k] = val([...path, k]);
        ws();
        if (s[i] === ",") {
          i++;
          continue;
        }
        if (s[i] === "}") return i++, o;
        fail("« , » ou « } » attendu (virgule oubliée ?)");
      }
    }
    if (c === "[") {
      i++;
      const a: unknown[] = [];
      ws();
      if (s[i] === "]") return i++, a;
      for (;;) {
        a.push(val([...path, a.length]));
        ws();
        if (s[i] === ",") {
          i++;
          ws();
          if (s[i] === "]") fail("virgule en trop avant « ] »");
          continue;
        }
        if (s[i] === "]") return i++, a;
        fail("« , » ou « ] » attendu (virgule oubliée ?)");
      }
    }
    if (c === '"') return str();
    const m = /^-?\d+(\.\d+)?([eE][+-]?\d+)?/.exec(s.slice(i));
    if (m) return (i += m[0].length), Number(m[0]);
    for (const [w, v] of [
      ["true", true],
      ["false", false],
      ["null", null],
    ] as const)
      if (s.startsWith(w, i)) return (i += w.length), v;
    if (c === "'") fail("les textes s'écrivent entre guillemets droits \" \", pas entre apostrophes");
    if (c === "«" || c === "“") fail("guillemets typographiques : utilise des guillemets droits \" \"");
    return fail(c === undefined ? "fin du texte inattendue (accolade ou crochet manquant ?)" : `caractère inattendu « ${c} »`);
  };
  const value = val([]);
  ws();
  if (i < s.length) fail("texte en trop après la fin du JSON");
  return {
    value,
    lineOf: (path) => {
      for (let n = path.length; n >= 0; n--) {
        const l = lines.get(JSON.stringify(path.slice(0, n)));
        if (l !== undefined) return l;
      }
      return undefined;
    },
  };
};
