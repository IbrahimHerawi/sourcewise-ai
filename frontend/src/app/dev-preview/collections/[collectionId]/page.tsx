import { redirect } from "next/navigation";

export default function RemovedCollectionPreviewRoute() {
  redirect("/dashboard/collections");
}
