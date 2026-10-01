import { useCallback, useEffect, useState } from "react";

import { api } from "../api";

type Setting = { id: number; key: string; value: string };
type SettingMeta = { label: string; description: string; unit: string; minimum?: number };

const settingDescriptions: Record<string, SettingMeta> = {
  max_night_shifts: {
    label: "จำนวนเวรดึกสูงสุดต่อเดือน",
    description: "กำหนดจำนวนเวรดึกสูงสุดที่บุคลากรหนึ่งคนควรได้รับภายในหนึ่งเดือน เพื่อช่วยควบคุมภาระงานและความเหนื่อยล้า",
    unit: "เวร/คน/เดือน",
    minimum: 0,
  },
  max_consecutive_work_days: {
    label: "จำนวนวันทำงานต่อเนื่องสูงสุด",
    description: "กำหนดจำนวนวันที่บุคลากรสามารถขึ้นเวรติดต่อกันได้ ก่อนที่ระบบควรจัดวันพักให้",
    unit: "วัน",
    minimum: 1,
  },
  minimum_rn_per_shift: {
    label: "จำนวนพยาบาลวิชาชีพขั้นต่ำต่อเวร",
    description: "กำหนดจำนวน RN ขั้นต่ำที่ต้องมีในแต่ละเวร เพื่อให้กำลังคนเพียงพอต่อการดูแลผู้ป่วย",
    unit: "คน/เวร",
    minimum: 0,
  },
  minimum_support_staff_per_window: {
    label: "จำนวนบุคลากรสนับสนุนขั้นต่ำต่อช่วงเวลา",
    description: "กำหนดจำนวนบุคลากรสนับสนุนขั้นต่ำที่ควรมีในแต่ละช่วงเวลาครอบคลุมของ ICU",
    unit: "คน/ช่วงเวลา",
    minimum: 0,
  },
};

function messageFrom(error: unknown): string {
  return error instanceof Error ? error.message : "ไม่สามารถบันทึกการตั้งค่าได้";
}

export default function SystemSettingsPanel(): JSX.Element {
  const [items, setItems] = useState<Setting[]>([]);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    try {
      const settings = await api<Setting[]>("/settings");
      setItems(settings);
      setDrafts(Object.fromEntries(settings.map(setting => [setting.key, setting.value])));
      setError("");
    } catch (requestError) { setError(messageFrom(requestError)); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function save(setting: Setting): Promise<void> {
    const value = (drafts[setting.key] ?? "").trim();
    if (!value) { setError("กรุณากรอกค่าก่อนบันทึก"); return; }
    const meta = settingDescriptions[setting.key];
    if (meta && (!Number.isInteger(Number(value)) || Number(value) < (meta.minimum ?? 0))) {
      setError(`ค่า “${meta.label}” ต้องเป็นจำนวนเต็มตั้งแต่ ${meta.minimum ?? 0} ขึ้นไป`);
      return;
    }
    setSavingKey(setting.key); setError(""); setNotice("");
    try {
      await api(`/settings/${setting.key}`, { method: "PUT", body: JSON.stringify({ key: setting.key, value }) });
      setNotice(`บันทึก “${meta?.label ?? setting.key}” เรียบร้อยแล้ว`);
      await load();
    } catch (requestError) { setError(messageFrom(requestError)); }
    finally { setSavingKey(null); }
  }

  return <section className="panel system-settings-panel">
    <div className="section-heading"><div><h2>การตั้งค่าระบบ</h2><p className="muted">ค่ากลางที่ระบบใช้ประกอบการตรวจสอบและจัดตารางเวร กรุณาแก้ไขเฉพาะเมื่อเข้าใจผลกระทบ</p></div><span className="admin-only-badge">สำหรับ Admin</span></div>
    <div className="settings-explanation"><strong>วิธีใช้งาน</strong><ol><li>อ่านคำอธิบายของรายการที่ต้องการปรับ</li><li>กรอกค่าใหม่เป็นตัวเลขตามหน่วยที่ระบุ</li><li>กด “บันทึก” เฉพาะแถวนั้น แล้วตรวจสอบข้อความยืนยัน</li></ol></div>
    {error && <p className="error" role="alert">{error}</p>}
    {notice && <p className="notice" role="status">{notice}</p>}
    <div className="system-settings-table-wrap"><table className="system-settings-table"><thead><tr><th>รายการตั้งค่า</th><th>คำอธิบาย</th><th>ค่าปัจจุบัน</th><th /></tr></thead><tbody>{items.map(setting => {
      const meta = settingDescriptions[setting.key];
      return <tr key={setting.id}><td><strong>{meta?.label ?? setting.key}</strong><small>{setting.key}</small></td><td><p>{meta?.description ?? "การตั้งค่าภายในระบบ โปรดตรวจสอบกับผู้ดูแลระบบก่อนแก้ไข"}</p>{meta && <span className="setting-unit">หน่วย: {meta.unit}</span>}</td><td><input aria-label={meta?.label ?? setting.key} type={meta ? "number" : "text"} min={meta?.minimum} step={meta ? 1 : undefined} value={drafts[setting.key] ?? setting.value} onChange={event => setDrafts(current => ({ ...current, [setting.key]: event.target.value }))} /></td><td><button className="small" disabled={savingKey === setting.key} onClick={() => { void save(setting); }}>{savingKey === setting.key ? "กำลังบันทึก..." : "บันทึก"}</button></td></tr>;
    })}</tbody></table></div>
    {!items.length && !error && <p className="muted">กำลังโหลดการตั้งค่าระบบ...</p>}
  </section>;
}
