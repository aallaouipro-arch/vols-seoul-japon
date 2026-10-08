import { AnimatePresence, motion } from "motion/react";
import { Bell, House, Search } from "lucide-react";
import { ToastProvider } from "./components/ui";
import { go, useRoute } from "./lib/nav";
import AlertsScreen from "./screens/Alerts";
import HomeScreen from "./screens/Home";
import SearchScreen from "./screens/Search";
import TripScreen from "./screens/Trip";

const TABS = [
  { path: "/", label: "Accueil", icon: House },
  { path: "/recherche", label: "Rechercher", icon: Search },
  { path: "/alertes", label: "Alertes", icon: Bell },
];

function BottomNav({ active }: { active: string }) {
  return (
    <nav className="fixed inset-x-0 bottom-0 z-40 flex justify-center px-4 pb-[max(14px,env(safe-area-inset-bottom))]">
      <div className="glass-strong flex w-full max-w-sm items-center justify-between rounded-[26px] p-1.5 shadow-2xl shadow-black/60">
        {TABS.map(({ path, label, icon: Icon }) => {
          const on = active === path;
          return (
            <button key={path} onClick={() => go(path)} className="relative flex flex-1 flex-col items-center gap-0.5 rounded-[20px] py-2" aria-current={on ? "page" : undefined}>
              {on && <motion.span layoutId="tab" className="bg-gradient-accent absolute inset-0 rounded-[20px] opacity-95" transition={{ type: "spring", damping: 28, stiffness: 340 }} />}
              <Icon size={20} className={`relative ${on ? "text-white" : "text-muted"}`} strokeWidth={on ? 2.4 : 2} />
              <span className={`relative text-[11px] font-semibold ${on ? "text-white" : "text-muted"}`}>{label}</span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}

export default function App() {
  const route = useRoute();
  const tab = route.startsWith("/alertes") ? "/alertes" : route.startsWith("/recherche") ? "/recherche" : "/";
  const page = route.startsWith("/voyage") ? "/voyage" : tab;
  const SCREENS: Record<string, () => React.JSX.Element> = { "/": HomeScreen, "/alertes": AlertsScreen, "/recherche": SearchScreen, "/voyage": TripScreen };
  const Screen = SCREENS[page] || HomeScreen;

  return (
    <ToastProvider>
      <main className="pb-nav relative z-10 mx-auto min-h-dvh max-w-xl px-4">
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={page}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.22, ease: "easeOut" }}
          >
            <Screen />
          </motion.div>
        </AnimatePresence>
        <footer className="mt-10 text-center text-[11px] leading-relaxed text-faint">
          Google Tracker · prix relevés sur Google Flights, frais de valises estimés.
          <br />
          Appli personnelle, non affiliée à Google.
        </footer>
      </main>
      <BottomNav active={tab} />
    </ToastProvider>
  );
}
