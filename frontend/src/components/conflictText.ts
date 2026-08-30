import type { ScheduleConflict } from "./conflictFilters";

function preferenceWeight(reason: string): string {
  return reason.match(/weight\s*(\d+)/i)?.[1] ?? "–";
}

/** Human-friendly Thai descriptions for ICU validator output. */
export function conflictReasonThai(conflict: Pick<ScheduleConflict, "code" | "reason">): string {
  const weight = preferenceWeight(conflict.reason);
  const messages: Record<string, string> = {
    SOFT_PREFERENCE_PREFER: `ระบบไม่สามารถจัดเวรที่บุคลากรต้องการได้ (ความสำคัญ ${weight}/5) เนื่องจากต้องรักษากฎความปลอดภัยและจำนวนบุคลากรให้เพียงพอ`,
    SOFT_PREFERENCE_AVOID: `ระบบจำเป็นต้องจัดเวรที่บุคลากรต้องการหลีกเลี่ยง (ความสำคัญ ${weight}/5) เพื่อให้ตารางผ่านกฎความปลอดภัยและมีบุคลากรเพียงพอ`,
    STAFFING_SHORTAGE: "จำนวนบุคลากรในเวรนี้ไม่ครบตามเกณฑ์ที่กำหนด",
    MIN_RN: "จำนวนพยาบาลวิชาชีพ (RN) ในเวรนี้ไม่ครบตามเกณฑ์",
    MAX_RN: "จำนวนพยาบาลวิชาชีพ (RN) ในเวรนี้เกินเกณฑ์",
    MIN_SUPPORT: "จำนวนผู้ช่วยพยาบาล/พนักงานช่วยเหลือ (PN/NA) ในเวรนี้ไม่ครบตามเกณฑ์",
    SENIOR_RN_REQUIRED: "เวรนี้ไม่มี Senior RN ปฏิบัติงานตามเกณฑ์",
    INCHARGE_REQUIRED: "เวรนี้ยังไม่ได้กำหนด Incharge ที่มีคุณสมบัติเหมาะสม",
    APPROVED_LEAVE: "มีการจัดเวรให้บุคลากรในวันที่ได้รับอนุมัติลาแล้ว",
    REST_AFTER_NIGHT: "เวลาพักหลังเวรดึกหรือเวร DE ไม่เพียงพอตามเกณฑ์ความปลอดภัย",
    SHIFT_OVERLAP: "บุคลากรถูกจัดเวรในช่วงเวลาที่ทับซ้อนกัน",
    ONE_SHIFT_PER_DAY: "บุคลากรหนึ่งคนถูกจัดมากกว่าหนึ่งเวรในวันเดียวกัน",
    D_DE_CONTINUATION: "มีเวร D แต่ไม่มีเวร DE สำหรับดูแลต่อเนื่องในช่วงกลางคืน",
    N_DE_TO_MORNING: "ไม่สามารถจัดเวรเช้าหรือ D ต่อจากเวรดึก/DE ได้ เพราะเวลาพักไม่ปลอดภัย",
    HEAD_NURSE_MORNING_ONLY: "หัวหน้าหอขึ้นเวรได้เฉพาะ AM หรือ D เท่านั้น",
  };
  return messages[conflict.code] ?? conflict.reason;
}
