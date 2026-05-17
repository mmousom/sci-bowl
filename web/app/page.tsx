import { redirect } from "next/navigation";

/** Root page — immediately redirects to the practice page. */
export default function RootPage(): never {
  redirect("/practice");
}
