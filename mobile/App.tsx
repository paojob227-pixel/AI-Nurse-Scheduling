import { useCallback, useEffect, useState } from "react";
import Constants from "expo-constants";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  RefreshControl,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaProvider, SafeAreaView } from "react-native-safe-area-context";

function defaultApiUrl(): string {
  // Expo's manifest contains the exact LAN host used by the scanned QR code.
  // Reusing it avoids a stale hard-coded address whenever Wi-Fi changes.
  const metroHost = Constants.expoConfig?.hostUri?.split(":")[0];
  return metroHost ? `http://${metroHost}:8001/api/v1` : "http://127.0.0.1:8001/api/v1";
}

const DEFAULT_API_URL = defaultApiUrl();

type User = { id: number; username: string; role: string; is_active: boolean };
type DashboardData = { active_staff: number; pending_leave_requests: number; today_assignments: number };
type SeniorPerson = { employee_code: string; name: string; shift_code: string };
type MyShift = {
  date: string;
  assignment: { shift_code: string; shift_name: string; time_range: string; is_incharge: boolean; schedule_status: string } | null;
  senior_rns: SeniorPerson[];
};
type Department = { id: number; name: string; code: string };
type Staff = { id: number; employee_code: string; first_name: string; last_name: string; position: string; is_senior_rn: boolean; active: boolean };
type Shift = { id: number; code: string; name: string; start_time: string | null; end_time: string | null; is_working_shift: boolean };
type ScheduleDetail = { id: number; staff_id: number; shift_type_id: number; work_date: string; locked: boolean };
type Schedule = { id: number; department_id: number; year: number; month: number; status: string; source: string; details: ScheduleDetail[] };
type Screen = "dashboard" | "schedule" | "account";

function cleanApiUrl(value: string) {
  return value.trim().replace(/\/$/, "").replace(/\/api\/v1$/, "") + "/api/v1";
}

function shiftDate(value: string, days: number) {
  const date = new Date(`${value}T12:00:00`);
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}

function localToday() {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
}

function previousDay(value: string) { return shiftDate(value, -1); }
function nextDay(value: string) { return shiftDate(value, 1); }
function formatThaiDate(value: string) { return new Intl.DateTimeFormat("th-TH", { weekday: "short", day: "numeric", month: "short", year: "numeric" }).format(new Date(`${value}T12:00:00`)); }

export default function App() {
  const [apiUrl, setApiUrl] = useState(DEFAULT_API_URL);
  const [username, setUsername] = useState("RN001");
  const [password, setPassword] = useState("");
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [screen, setScreen] = useState<Screen>("dashboard");
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [myShift, setMyShift] = useState<MyShift | null>(null);
  const [wardSchedule, setWardSchedule] = useState<Schedule | null>(null);
  const [wardStaff, setWardStaff] = useState<Staff[]>([]);
  const [shiftTypes, setShiftTypes] = useState<Shift[]>([]);
  const [scheduleDate, setScheduleDate] = useState(localToday);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const request = useCallback(async <T,>(path: string, options: RequestInit = {}, accessToken = token): Promise<T> => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 12_000);
    let response: Response;
    try {
      response = await fetch(`${cleanApiUrl(apiUrl)}${path}`, {
        ...options,
        signal: controller.signal,
        headers: { "Content-Type": "application/json", ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}), ...options.headers },
      });
    } catch (reason) {
      if (reason instanceof Error && reason.name === "AbortError") throw new Error("เชื่อมต่อ Backend ไม่สำเร็จภายใน 12 วินาที กรุณาตรวจสอบว่าโทรศัพท์อยู่ Wi‑Fi เดียวกับคอมพิวเตอร์ และใช้ที่อยู่ Backend ให้ถูกต้อง");
      throw new Error("ไม่สามารถเชื่อมต่อ Backend ได้ กรุณาตรวจสอบ Wi‑Fi และที่อยู่ Backend");
    } finally {
      clearTimeout(timeout);
    }
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : "ไม่สามารถเชื่อมต่อกับระบบได้");
    return body as T;
  }, [apiUrl, token]);

  const loadHome = useCallback(async () => {
    if (!token) return;
    const [summary, shift] = await Promise.all([
      request<DashboardData>("/dashboard"),
      request<MyShift>("/dashboard/my-shift"),
    ]);
    setDashboard(summary);
    setMyShift(shift);
  }, [request, token]);

  const loadWardSchedule = useCallback(async () => {
    if (!token) return;
    const [year, month] = scheduleDate.split("-").map(Number);
    const [departments, staff, shifts] = await Promise.all([
      request<Department[]>("/departments"),
      request<Staff[]>("/staff"),
      request<Shift[]>("/shift-types"),
    ]);
    const department = departments[0];
    if (!department) { setWardSchedule(null); setWardStaff([]); setShiftTypes(shifts); return; }
    const schedules = await request<Schedule[]>(`/schedules?department_id=${department.id}&year=${year}&month=${month}`);
    setWardSchedule(schedules[0] ?? null);
    setWardStaff(staff.filter(person => person.active));
    setShiftTypes(shifts);
  }, [request, scheduleDate, token]);

  useEffect(() => { if (token) loadHome().catch((reason: Error) => setError(reason.message)); }, [token, loadHome]);
  useEffect(() => { if (token) loadWardSchedule().catch((reason: Error) => setError(reason.message)); }, [token, loadWardSchedule]);

  async function login() {
    setLoading(true); setError("");
    try {
      const tokens = await request<{ access_token: string }>("/auth/login", { method: "POST", body: JSON.stringify({ username, password }) }, null);
      setToken(tokens.access_token);
      const currentUser = await request<User>("/auth/me", {}, tokens.access_token);
      setUser(currentUser);
      setPassword("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "เข้าสู่ระบบไม่สำเร็จ");
    } finally { setLoading(false); }
  }

  async function refresh() {
    setRefreshing(true); setError("");
    try { await loadHome(); } catch (reason) { setError(reason instanceof Error ? reason.message : "ไม่สามารถรีเฟรชข้อมูลได้"); } finally { setRefreshing(false); }
  }

  function logout() {
    setToken(null); setUser(null); setDashboard(null); setMyShift(null); setWardSchedule(null); setWardStaff([]); setScreen("dashboard"); setError("");
  }

  if (!token || !user) return <SafeAreaProvider><LoginScreen apiUrl={apiUrl} setApiUrl={setApiUrl} username={username} setUsername={setUsername} password={password} setPassword={setPassword} loading={loading} error={error} onLogin={login} /></SafeAreaProvider>;

  return (
    <SafeAreaProvider><SafeAreaView style={styles.safe}>
      <StatusBar barStyle="light-content" />
      <View style={styles.header}><View><Text style={styles.headerEyebrow}>ICU CARE WORKFORCE</Text><Text style={styles.headerTitle}>ICU Schedule</Text></View><View style={styles.avatar}><Text style={styles.avatarText}>{user.username.slice(0, 1)}</Text></View></View>
      <ScrollView contentContainerStyle={styles.content} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor="#2563eb" />}>
        {error ? <View style={styles.errorBox}><Text style={styles.errorText}>{error}</Text></View> : null}
        {screen === "dashboard" && <Dashboard dashboard={dashboard} myShift={myShift} schedule={wardSchedule} staff={wardStaff} shifts={shiftTypes} onViewSchedule={() => setScreen("schedule")} />}
        {screen === "schedule" && <WardSchedule schedule={wardSchedule} staff={wardStaff} shifts={shiftTypes} workDate={scheduleDate} onPrevious={() => setScheduleDate(previousDay(scheduleDate))} onNext={() => setScheduleDate(nextDay(scheduleDate))} onRefresh={() => loadWardSchedule().catch((reason: Error) => setError(reason.message))} />}
        {screen === "account" && <Account user={user} apiUrl={apiUrl} onLogout={logout} />}
      </ScrollView>
      <View style={styles.tabBar}>
        <Tab icon="⌂" label="ภาพรวม" active={screen === "dashboard"} onPress={() => setScreen("dashboard")} />
        <Tab icon="▦" label="ตารางเวร" active={screen === "schedule"} onPress={() => setScreen("schedule")} />
        <Tab icon="◉" label="บัญชี" active={screen === "account"} onPress={() => setScreen("account")} />
      </View>
    </SafeAreaView></SafeAreaProvider>
  );
}

function LoginScreen(props: { apiUrl: string; setApiUrl: (value: string) => void; username: string; setUsername: (value: string) => void; password: string; setPassword: (value: string) => void; loading: boolean; error: string; onLogin: () => void }) {
  return <SafeAreaView style={styles.loginSafe}><StatusBar barStyle="dark-content" /><ScrollView contentContainerStyle={styles.loginShell}><View style={styles.loginBrand}><View style={styles.loginMark}><Text style={styles.loginMarkText}>+</Text></View><Text style={styles.loginBrandTitle}>ICU Schedule</Text><Text style={styles.loginBrandSub}>CARE WORKFORCE</Text></View><View style={styles.loginCard}><Text style={styles.eyebrow}>AI NURSE SCHEDULING</Text><Text style={styles.loginTitle}>เข้าสู่ระบบ</Text><Text style={styles.loginDescription}>จัดการตารางเวร ICU ได้จากมือถือ</Text><Field label="ชื่อผู้ใช้" value={props.username} onChangeText={props.setUsername} autoCapitalize="characters" placeholder="เช่น RN001" /><Field label="รหัสผ่าน" value={props.password} onChangeText={props.setPassword} secureTextEntry placeholder="กรอกรหัสผ่าน" /><Field label="ที่อยู่ Backend" value={props.apiUrl} onChangeText={props.setApiUrl} autoCapitalize="none" placeholder="http://192.168.x.x:8001/api/v1" /><Text style={styles.helper}>มือถือและคอมพิวเตอร์ต้องอยู่ Wi‑Fi เดียวกัน</Text>{props.error ? <View style={styles.errorBox}><Text style={styles.errorText}>{props.error}</Text></View> : null}<Pressable style={({ pressed }) => [styles.primaryButton, pressed && styles.pressed, props.loading && styles.disabled]} disabled={props.loading} onPress={props.onLogin}>{props.loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.primaryButtonText}>เข้าสู่ระบบ</Text>}</Pressable></View></ScrollView></SafeAreaView>;
}

function Dashboard({ dashboard, myShift, schedule, staff, shifts, onViewSchedule }: { dashboard: DashboardData | null; myShift: MyShift | null; schedule: Schedule | null; staff: Staff[]; shifts: Shift[]; onViewSchedule: () => void }) {
  const date = myShift?.date ?? localToday();
  const staffById = new Map(staff.map(person => [person.id, person]));
  const shiftById = new Map(shifts.map(shift => [shift.id, shift]));
  const wardSeniors: SeniorPerson[] = schedule?.details.filter(item => item.work_date === date).map(item => ({ item, person: staffById.get(item.staff_id) })).filter((entry): entry is { item: ScheduleDetail; person: Staff } => Boolean(entry.person?.is_senior_rn)).map(({ item, person }) => ({ employee_code: person.employee_code, name: `${person.first_name} ${person.last_name}`, shift_code: `เวร ${shiftById.get(item.shift_type_id)?.code ?? "-"}` })) ?? [];
  const seniors = wardSeniors.length ? wardSeniors : (myShift?.senior_rns ?? []);
  return <><View style={styles.welcome}><Text style={styles.eyebrow}>ICU OPERATIONS</Text><Text style={styles.welcomeTitle}>ภาพรวมวันนี้</Text><Text style={styles.welcomeText}>ข้อมูลเวรส่วนตัวและกำลังคนของหอ ICU จากตารางชุดเดียวกัน</Text></View><View style={styles.metrics}><Metric label="บุคลากรพร้อม" value={dashboard?.active_staff} icon="♙" tint="#ddecff" /><Metric label="ลารออนุมัติ" value={dashboard?.pending_leave_requests} icon="◷" tint="#fff0cf" /><Metric label="เวรทั้งหอวันนี้" value={dashboard?.today_assignments} icon="▦" tint="#ede4ff" /></View><View style={styles.shiftCard}><View style={styles.cardHeader}><View><Text style={styles.eyebrow}>MY SHIFT TODAY</Text><Text style={styles.cardTitle}>เวรของฉันวันนี้</Text></View><Text style={styles.datePill}>{date}</Text></View>{myShift?.assignment ? <View style={styles.shiftMain}><View style={styles.shiftCode}><Text style={styles.shiftCodeText}>{myShift.assignment.shift_code}</Text></View><View><Text style={styles.shiftName}>{myShift.assignment.shift_name}</Text><Text style={styles.shiftTime}>เวลา {myShift.assignment.time_range}{myShift.assignment.is_incharge ? " · Incharge" : ""}</Text></View></View> : <View style={styles.empty}><Text style={styles.emptyTitle}>วันนี้คุณไม่มีเวร</Text><Text style={styles.emptyText}>ตัวเลข “เวรทั้งหอวันนี้” ด้านบนเป็นจำนวนเวรของทุกคน ไม่ใช่เวรส่วนตัว</Text></View>}<SeniorList people={seniors} title="Senior RN ที่ขึ้นเวรวันนี้" /><Pressable style={styles.outlineButton} onPress={onViewSchedule}><Text style={styles.outlineButtonText}>ดูตารางเวรทั้งหอ</Text></Pressable></View><View style={styles.infoCard}><Text style={styles.infoIcon}>✦</Text><View><Text style={styles.infoTitle}>AI Scheduling เป็นผู้ช่วยตัดสินใจ</Text><Text style={styles.infoText}>Mobile แสดงข้อมูลจริงแบบอ่านอย่างเดียว ส่วนการตรวจ อนุมัติ และเผยแพร่ทำในเว็บ</Text></View></View></>;
}

function SeniorList({ people, title }: { people: SeniorPerson[]; title: string }) {
  return <View style={styles.seniorBlock}><Text style={styles.seniorTitle}>{title}</Text>{people.length ? people.map(person => <View style={styles.seniorRow} key={`${person.employee_code}-${person.shift_code}`}><View style={styles.seniorDot}><Text>✓</Text></View><View><Text style={styles.seniorName}>{person.name}</Text><Text style={styles.seniorMeta}>{person.employee_code} · {person.shift_code}</Text></View></View>) : <Text style={styles.emptyText}>ยังไม่มี Senior RN ในตารางวันนี้ — ให้ Head Nurse ตรวจสอบก่อนเผยแพร่</Text>}</View>;
}

function WardSchedule({ schedule, staff, shifts, workDate, onPrevious, onNext, onRefresh }: { schedule: Schedule | null; staff: Staff[]; shifts: Shift[]; workDate: string; onPrevious: () => void; onNext: () => void; onRefresh: () => void }) {
  const staffById = new Map(staff.map(person => [person.id, person]));
  const shiftById = new Map(shifts.map(shift => [shift.id, shift]));
  const assignments = schedule?.details.filter(item => item.work_date === workDate).map(item => ({ item, person: staffById.get(item.staff_id), shift: shiftById.get(item.shift_type_id) })).filter(entry => entry.person && entry.shift) ?? [];
  return <><Text style={styles.screenTitle}>ตารางเวรรายวัน</Text><Text style={styles.screenSubtitle}>ข้อมูลจากตาราง Manual ฉบับเดียวกับบนเว็บ</Text><View style={styles.dateControl}><Pressable style={styles.dayButton} onPress={onPrevious}><Text style={styles.dayButtonText}>‹</Text></Pressable><View><Text style={styles.scheduleDate}>{formatThaiDate(workDate)}</Text><Text style={styles.scheduleState}>{schedule ? (schedule.status === "published" ? "เผยแพร่แล้ว" : "ฉบับร่าง · อาจมีการเปลี่ยนแปลง") : "ไม่พบตารางของเดือนนี้"}</Text></View><Pressable style={styles.dayButton} onPress={onNext}><Text style={styles.dayButtonText}>›</Text></Pressable></View><Pressable style={styles.refreshButton} onPress={onRefresh}><Text style={styles.refreshText}>↻ รีเฟรชข้อมูล</Text></Pressable>{schedule ? <View style={styles.wardCard}><Text style={styles.wardTitle}>เวรที่กำหนดในหอ ({assignments.length})</Text>{assignments.length ? assignments.map(({ item, person, shift }) => <View style={styles.wardRow} key={item.id}><View style={styles.wardShift}><Text style={styles.wardShiftText}>{shift!.code}</Text></View><View style={styles.wardPerson}><Text style={styles.wardName}>{person!.first_name} {person!.last_name}</Text><Text style={styles.wardMeta}>{person!.employee_code} · {person!.position} · {shift!.start_time?.slice(0, 5)}–{shift!.end_time?.slice(0, 5)}</Text></View>{person!.is_senior_rn ? <Text style={styles.seniorBadge}>Senior</Text> : null}</View>) : <View style={styles.empty}><Text style={styles.emptyTitle}>ยังไม่มีเวรในวันที่เลือก</Text><Text style={styles.emptyText}>เลือกวันก่อนหน้า/ถัดไปเพื่อตรวจตารางในเดือนนี้</Text></View>}</View> : <View style={styles.wardCard}><Text style={styles.emptyTitle}>ไม่พบตารางของเดือนนี้</Text><Text style={styles.emptyText}>ตารางอาจยังไม่ได้สร้าง หรือให้เลือกวันในเดือนที่มีตาราง</Text></View>}</>;
}

function Account({ user, apiUrl, onLogout }: { user: User; apiUrl: string; onLogout: () => void }) {
  return <><Text style={styles.screenTitle}>บัญชีผู้ใช้</Text><Text style={styles.screenSubtitle}>ข้อมูลการเชื่อมต่อของแอปมือถือ</Text><View style={styles.accountCard}><View style={styles.accountAvatar}><Text style={styles.accountAvatarText}>{user.username.slice(0, 1)}</Text></View><Text style={styles.accountName}>{user.username}</Text><Text style={styles.rolePill}>{user.role.replace("_", " ")}</Text><View style={styles.accountLine}><Text style={styles.accountLabel}>Backend</Text><Text style={styles.accountValue}>{cleanApiUrl(apiUrl)}</Text></View><Pressable style={styles.logoutButton} onPress={() => Alert.alert("ออกจากระบบ", "ต้องการออกจากระบบบนอุปกรณ์นี้หรือไม่", [{ text: "ยกเลิก", style: "cancel" }, { text: "ออกจากระบบ", style: "destructive", onPress: onLogout }])}><Text style={styles.logoutText}>ออกจากระบบ</Text></Pressable></View></>;
}

function Field(props: { label: string; value: string; onChangeText: (value: string) => void; placeholder: string; secureTextEntry?: boolean; autoCapitalize?: "none" | "characters" }) { return <View style={styles.field}><Text style={styles.fieldLabel}>{props.label}</Text><TextInput style={styles.input} value={props.value} onChangeText={props.onChangeText} placeholder={props.placeholder} placeholderTextColor="#90a0b8" secureTextEntry={props.secureTextEntry} autoCapitalize={props.autoCapitalize} autoCorrect={false} /></View>; }
function Metric({ label, value, icon, tint }: { label: string; value: number | undefined; icon: string; tint: string }) { return <View style={styles.metric}><View style={[styles.metricIcon, { backgroundColor: tint }]}><Text>{icon}</Text></View><Text style={styles.metricValue}>{value ?? "–"}</Text><Text style={styles.metricLabel}>{label}</Text></View>; }
function Tab({ icon, label, active, onPress }: { icon: string; label: string; active: boolean; onPress: () => void }) { return <Pressable style={styles.tab} onPress={onPress}><Text style={[styles.tabIcon, active && styles.tabActive]}>{icon}</Text><Text style={[styles.tabLabel, active && styles.tabActive]}>{label}</Text></Pressable>; }

const styles = StyleSheet.create({
  seniorBlock: { marginTop: 18, paddingTop: 15, borderTopWidth: 1, borderTopColor: "#e8eef7" },
  dateControl: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: 17, backgroundColor: "#fff", padding: 15, borderRadius: 17, shadowColor: "#1d416f", shadowOpacity: .08, shadowRadius: 12, elevation: 2 },
  dayButton: { width: 40, height: 40, borderRadius: 12, alignItems: "center", justifyContent: "center", backgroundColor: "#eaf2ff" },
  dayButtonText: { color: "#2763bc", fontSize: 28, lineHeight: 31 },
  scheduleDate: { color: "#203d66", fontWeight: "800", textAlign: "center", fontSize: 15 },
  scheduleState: { color: "#71839c", textAlign: "center", fontSize: 11, marginTop: 4 },
  refreshButton: { alignSelf: "flex-end", marginTop: 12, paddingVertical: 8, paddingHorizontal: 11, borderRadius: 9, backgroundColor: "#eaf2ff" },
  refreshText: { color: "#2c64b5", fontSize: 12, fontWeight: "700" },
  wardCard: { marginTop: 2, padding: 16, backgroundColor: "#fff", borderRadius: 18, shadowColor: "#1d416f", shadowOpacity: .08, shadowRadius: 13, elevation: 2 },
  wardTitle: { color: "#203d66", fontWeight: "800", fontSize: 16, marginBottom: 4 },
  wardRow: { flexDirection: "row", alignItems: "center", paddingVertical: 13, borderBottomWidth: 1, borderBottomColor: "#edf1f7" },
  wardShift: { width: 42, height: 42, borderRadius: 12, justifyContent: "center", alignItems: "center", backgroundColor: "#e8f1ff" },
  wardShiftText: { color: "#2461bd", fontWeight: "800" },
  wardPerson: { flex: 1, marginLeft: 11 },
  wardName: { color: "#27486d", fontWeight: "800" },
  wardMeta: { color: "#71829a", fontSize: 11, marginTop: 3 },
  seniorBadge: { color: "#936400", backgroundColor: "#fff1cb", fontSize: 10, fontWeight: "800", paddingHorizontal: 7, paddingVertical: 4, borderRadius: 99 },
  safe: { flex: 1, backgroundColor: "#f4f8ff" }, loginSafe: { flex: 1, backgroundColor: "#eef5ff" }, content: { padding: 18, paddingBottom: 106 }, header: { padding: 18, paddingTop: 12, backgroundColor: "#153a73", flexDirection: "row", justifyContent: "space-between", alignItems: "center" }, headerEyebrow: { color: "#a8c9ff", fontSize: 10, fontWeight: "800", letterSpacing: 1.5 }, headerTitle: { color: "#fff", fontSize: 22, fontWeight: "800", marginTop: 3 }, avatar: { width: 40, height: 40, borderRadius: 20, backgroundColor: "#dcecff", alignItems: "center", justifyContent: "center" }, avatarText: { color: "#1a4e98", fontWeight: "800", fontSize: 18 }, loginShell: { flexGrow: 1, justifyContent: "center", padding: 23 }, loginBrand: { alignItems: "center", marginBottom: 25 }, loginMark: { width: 52, height: 52, borderRadius: 16, backgroundColor: "#1e62c4", alignItems: "center", justifyContent: "center", shadowColor: "#1f5fb9", shadowOpacity: .25, shadowRadius: 15, elevation: 5 }, loginMarkText: { color: "#fff", fontSize: 33, fontWeight: "500" }, loginBrandTitle: { fontSize: 26, fontWeight: "800", color: "#173b70", marginTop: 12 }, loginBrandSub: { color: "#607ca6", fontSize: 10, letterSpacing: 2, marginTop: 3, fontWeight: "800" }, loginCard: { backgroundColor: "#fff", padding: 23, borderRadius: 22, shadowColor: "#174175", shadowOpacity: .12, shadowRadius: 25, elevation: 3 }, eyebrow: { color: "#2c6fd1", fontSize: 10, fontWeight: "800", letterSpacing: 1.4 }, loginTitle: { fontSize: 26, fontWeight: "800", color: "#152f59", marginTop: 7 }, loginDescription: { color: "#657792", marginTop: 6, marginBottom: 19, lineHeight: 21 }, field: { marginBottom: 14 }, fieldLabel: { fontWeight: "700", fontSize: 13, color: "#354d70", marginBottom: 7 }, input: { borderWidth: 1, borderColor: "#d6e2f2", borderRadius: 12, paddingHorizontal: 13, paddingVertical: 12, color: "#17335e", backgroundColor: "#fbfdff" }, helper: { color: "#75869f", fontSize: 12, lineHeight: 18, marginTop: -2, marginBottom: 15 }, primaryButton: { backgroundColor: "#2464d1", borderRadius: 12, alignItems: "center", paddingVertical: 14, marginTop: 2 }, primaryButtonText: { color: "#fff", fontWeight: "800", fontSize: 15 }, pressed: { opacity: .82 }, disabled: { opacity: .55 }, errorBox: { backgroundColor: "#fff0f2", borderColor: "#ffcad1", borderWidth: 1, padding: 11, borderRadius: 11, marginBottom: 14 }, errorText: { color: "#b4233b", lineHeight: 19 }, welcome: { padding: 21, borderRadius: 20, backgroundColor: "#1d5eb7", shadowColor: "#1d5eb7", shadowOpacity: .18, shadowRadius: 15, elevation: 3 }, welcomeTitle: { color: "#fff", fontSize: 28, fontWeight: "800", marginTop: 6 }, welcomeText: { color: "#deecff", lineHeight: 21, marginTop: 8 }, metrics: { flexDirection: "row", gap: 9, marginTop: 14 }, metric: { flex: 1, backgroundColor: "#fff", borderRadius: 16, padding: 12, minHeight: 112, shadowColor: "#1d416f", shadowOpacity: .07, shadowRadius: 10, elevation: 1 }, metricIcon: { width: 29, height: 29, borderRadius: 9, alignItems: "center", justifyContent: "center" }, metricValue: { color: "#1b365f", fontSize: 23, fontWeight: "800", marginTop: 10 }, metricLabel: { color: "#6e809b", fontSize: 11, marginTop: 2, lineHeight: 15 }, shiftCard: { marginTop: 15, padding: 18, borderRadius: 19, backgroundColor: "#fff", shadowColor: "#1d416f", shadowOpacity: .08, shadowRadius: 13, elevation: 2 }, cardHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start" }, cardTitle: { color: "#1a355d", fontSize: 19, fontWeight: "800", marginTop: 4 }, datePill: { color: "#47658d", backgroundColor: "#edf4ff", paddingHorizontal: 9, paddingVertical: 5, borderRadius: 99, fontSize: 11 }, shiftMain: { flexDirection: "row", alignItems: "center", gap: 13, marginTop: 16 }, shiftCode: { width: 58, height: 58, borderRadius: 16, alignItems: "center", justifyContent: "center", backgroundColor: "#2b68ce" }, shiftCodeText: { color: "#fff", fontSize: 19, fontWeight: "800" }, shiftName: { color: "#1b365f", fontSize: 17, fontWeight: "800" }, shiftTime: { color: "#627795", marginTop: 4 }, incharge: { color: "#9a6300", fontWeight: "700", marginTop: 5 }, outlineButton: { borderWidth: 1, borderColor: "#cfe0f6", borderRadius: 11, alignItems: "center", paddingVertical: 11, marginTop: 18 }, outlineButtonText: { color: "#2760b7", fontWeight: "700", fontSize: 13 }, empty: { paddingTop: 20 }, emptyTitle: { color: "#304b70", fontWeight: "800", fontSize: 16 }, emptyText: { color: "#71839d", lineHeight: 20, marginTop: 6 }, infoCard: { flexDirection: "row", gap: 12, padding: 16, marginTop: 15, borderRadius: 16, backgroundColor: "#f5f3ff", borderWidth: 1, borderColor: "#e3ddff" }, infoIcon: { color: "#7359bd", fontSize: 22 }, infoTitle: { color: "#443b78", fontWeight: "800" }, infoText: { color: "#6d668f", fontSize: 12, lineHeight: 18, marginTop: 4, flexShrink: 1 }, screenTitle: { color: "#19365f", fontSize: 25, fontWeight: "800", marginTop: 4 }, screenSubtitle: { color: "#71829a", marginTop: 5 }, divider: { height: 1, backgroundColor: "#e6edf6", marginVertical: 19 }, seniorTitle: { color: "#29466d", fontWeight: "800", fontSize: 15 }, seniorRow: { flexDirection: "row", alignItems: "center", gap: 10, paddingTop: 13 }, seniorDot: { width: 28, height: 28, borderRadius: 14, alignItems: "center", justifyContent: "center", backgroundColor: "#def7ea" }, seniorName: { color: "#234768", fontWeight: "700" }, seniorMeta: { color: "#71849d", fontSize: 12, marginTop: 2 }, accountCard: { alignItems: "center", backgroundColor: "#fff", marginTop: 17, padding: 22, borderRadius: 19, shadowColor: "#1d416f", shadowOpacity: .08, shadowRadius: 13, elevation: 2 }, accountAvatar: { width: 70, height: 70, borderRadius: 35, alignItems: "center", justifyContent: "center", backgroundColor: "#dcebff" }, accountAvatarText: { color: "#2560b8", fontSize: 30, fontWeight: "800" }, accountName: { color: "#203d66", fontSize: 20, fontWeight: "800", marginTop: 11 }, rolePill: { color: "#2d64b3", backgroundColor: "#e8f1ff", paddingHorizontal: 10, paddingVertical: 5, borderRadius: 99, fontSize: 12, marginTop: 6 }, accountLine: { width: "100%", marginTop: 22, paddingTop: 14, borderTopWidth: 1, borderTopColor: "#edf1f6" }, accountLabel: { color: "#74859c", fontSize: 12 }, accountValue: { color: "#36577e", fontSize: 12, marginTop: 4 }, logoutButton: { width: "100%", alignItems: "center", paddingVertical: 12, borderRadius: 11, backgroundColor: "#fff0f2", marginTop: 19 }, logoutText: { color: "#bb2a43", fontWeight: "800" }, tabBar: { position: "absolute", left: 12, right: 12, bottom: 10, flexDirection: "row", justifyContent: "space-around", paddingVertical: 8, borderRadius: 18, backgroundColor: "#fff", shadowColor: "#152f59", shadowOpacity: .16, shadowRadius: 15, elevation: 7 }, tab: { alignItems: "center", minWidth: 76, paddingVertical: 3 }, tabIcon: { color: "#8291a8", fontSize: 20 }, tabLabel: { color: "#8291a8", fontSize: 11, marginTop: 2 }, tabActive: { color: "#2563c7", fontWeight: "800" },
});
