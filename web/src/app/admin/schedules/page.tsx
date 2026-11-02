"use client";

import { Suspense } from "react";
import { Text } from "@chakra-ui/react";
import ScheduleEditor from "@/features/schedules/ScheduleEditor";

export default function SchedulesPage() {
  return (
    <Suspense fallback={<Text p={8}>Opening service schedule…</Text>}>
      <ScheduleEditor />
    </Suspense>
  );
}
