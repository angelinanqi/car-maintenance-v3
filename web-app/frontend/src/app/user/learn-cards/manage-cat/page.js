import { redirect } from "next/navigation";

// Category management is not part of the local prototype.
export default function ManageCategories() {
  redirect("/user/learn-cards");
}
