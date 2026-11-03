/**
 * Hash — a long hash or id shown by its first characters, with the full value one hover away.
 * Screen readers read the short form too; nobody needs forty characters read aloud.
 */
import { shortHash } from "@/lib/format";

export default function Hash({ value, length = 8 }: { value: string; length?: number }) {
  return (
    <code className="hash" title={value}>
      {shortHash(value, length)}
    </code>
  );
}
