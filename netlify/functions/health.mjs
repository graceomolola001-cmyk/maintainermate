import {createApi} from '../lib/api.mjs';
const handle = createApi();
export default request => handle(request, 'health');
export const config = {path: '/health'};
