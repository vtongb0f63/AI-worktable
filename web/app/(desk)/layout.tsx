import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import Shell from '@/components/planner/Shell';
export default async function DeskLayout({children}:{children:React.ReactNode}) {
 const jar=await cookies(); const session=jar.get('session'); if(!session)redirect('/login');
 const response=await fetch(`${process.env.API_INTERNAL_URL||'http://127.0.0.1:8000'}/api/me`,{headers:{Cookie:`session=${session.value}`},cache:'no-store'});
 if(response.status===401||response.status===403)redirect('/login');
 if(!response.ok)throw new Error('暂时无法连接工作台，请刷新重试');
 const user=await response.json();return <Shell username={user.username}>{children}</Shell>;
}
