import SettingsView from '../views/SettingsView';
import LeftNav from '../components/sidebar/LeftNav';

export default function SettingsPage() {
  return (
    <>
      <LeftNav active="settings" />
      <SettingsView />
    </>
  );
}
