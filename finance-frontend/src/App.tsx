import {BrowserRouter, Routes, Route} from 'react-router-dom';
import {Layout} from './components/common/Layout';
import {Dashboard} from './pages/Dashboard';
import {Transactions} from './pages/Transactions';
// import { Budgets } from './pages/Budgets';
// import { Goals } from './pages/Goals';
// import { Analytics } from './pages/Analytics';
// import { Settings } from './pages/Settings';

function App() {
    return (
        <BrowserRouter>
            <Routes>
                <Route path="/" element={<Layout/>}>
                    <Route index element={<Dashboard/>}/>
                    <Route path="transactions" element={<Transactions/>}/>
                    {/*<Route path="budgets" element={<Budgets />} />*/}
                    {/*<Route path="goals" element={<Goals />} />*/}
                    {/*<Route path="analytics" element={<Analytics />} />*/}
                    {/*<Route path="settings" element={<Settings />} />*/}
                </Route>
            </Routes>
        </BrowserRouter>
    );
}

export default App;