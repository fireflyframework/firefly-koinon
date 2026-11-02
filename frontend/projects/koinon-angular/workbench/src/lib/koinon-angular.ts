import {KoinonTextPipe} from './foundations/i18n';
// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {CdkTrapFocus} from '@angular/cdk/a11y';
import type {OverlayRef} from '@angular/cdk/overlay';
import type {createDialogOverlay} from './services/dialog-overlay';
import {NgComponentOutlet} from '@angular/common';
import {KoinonAccountPage} from './organisms/account-page';
import {KoinonWorkbenchDialogs} from './organisms/workbench-dialogs';
import {ChangeDetectionStrategy,Component,HostListener,Input,Output,EventEmitter,OnInit,OnChanges,OnDestroy,PendingTasks,ViewChild,TemplateRef,ViewContainerRef,ElementRef,ViewEncapsulation,booleanAttribute,computed,effect,inject,signal,type SimpleChanges,type Type,Injector,afterNextRender} from '@angular/core';
import type {BrandingValues,CatalogEntry,Citation,KoinonClient,KoinonTransport,QueryResponse,ResourceKind,Membership} from '@fireflyframework/koinon-sdk';
import {KoinonI18n} from './foundations/i18n';
import {KoinonAccount} from './services/account';
import {KoinonBranding} from './services/branding';
import {brandStyles,brandImage,brandSymbol} from './services/branding-values';
import {KoinonFontLoader} from './services/font-loader';
import {KoinonFacade} from './koinon-facade';
import {KOINON_ACTIVITY_LOADER,KOINON_COMMUNICATIONS_LOADER,KOINON_CHAT_LOADER,KOINON_SETTINGS_LOADER,KOINON_INVITATION_LOADER,KOINON_SHARED_CONVERSATION_LOADER} from './services/chat-loader';
import {KoinonAssistant} from './services/assistant';
import {KoinonClientContext} from './services/client-context';
import {folderTrail,isSystemManaged,friendlyKind,isFolder,nextFolderKind} from './services/library-tree';
import {KoinonCommandPalette,type KoinonCommand} from './organisms/command-palette';
import {KoinonSignIn} from './organisms/sign-in';
import {KoinonShell,type PrimaryDestination} from './organisms/shell';
import {KoinonLibraryTemplate} from './templates/library-template';
import {KoinonInspector} from './organisms/inspector';
import {KoinonTableLineagePanel} from './organisms/table-lineage-panel';
import {KoinonTableLineage} from './services/table-lineage';
import {KoinonButton} from './atoms/button';
import {KoinonIcon} from './atoms/icon';
import {KoinonSkeleton} from './atoms/skeleton';
import type {KoinonScope} from './models';
type Dialog='uploads'|'move'|'sign-out'|'account'|'archived'|'tree'|'add'|'create'|'edit'|'upload'|'archive'|'query'|'lineage'|'citation';
@Component({selector:'ffk-workbench',imports:[KoinonSignIn,KoinonAccountPage,CdkTrapFocus,KoinonTableLineagePanel,KoinonTextPipe,KoinonCommandPalette,NgComponentOutlet,KoinonWorkbenchDialogs,KoinonShell,KoinonLibraryTemplate,KoinonInspector,KoinonButton,KoinonIcon,KoinonSkeleton],providers:[KoinonBranding,KoinonTableLineage,KoinonFontLoader,KoinonI18n,KoinonAccount,KoinonClientContext,KoinonFacade,KoinonAssistant],templateUrl:'./workbench.html',styleUrl:'./workbench.scss',host:{'[class.koinon-dark]':"theme==='dark'",'[attr.lang]':'i18n.preferences().locale'},encapsulation:ViewEncapsulation.ShadowDom,changeDetection:ChangeDetectionStrategy.OnPush})
export class KoinonWorkbench implements OnInit,OnChanges,OnDestroy{
 readonly sharedConversationComponent=signal<Type<unknown>|null>(null);
 readonly sharedConversationError=signal('');
 private readonly sharedConversationLoader=inject(KOINON_SHARED_CONVERSATION_LOADER,{optional:true});
 readonly sharedConversationActions={assistantName:()=>this.brand.value().assistant_name,closed:()=>this.dismissSharedConversation(),resourceRequested:(source:{asset_id:string})=>{this.dismissSharedConversation();void this.openChatResource(source.asset_id);}};
 dismissSharedConversation(){this.sharedConversationDismissed.emit();this.focusMainHeading();}
 async loadSharedConversation(){
  if(this.sharedConversationComponent())return;
  this.sharedConversationError.set('');
  if(!this.sharedConversationLoader){this.sharedConversationError.set('Shared conversation support is not enabled in this application.');return;}
  try{this.sharedConversationComponent.set(await this.sharedConversationLoader());}
  catch{this.sharedConversationError.set('The shared conversation could not be opened. Try again.');}
 }
 readonly activityComponent=signal<Type<unknown>|null>(null);private readonly activityLoader=inject(KOINON_ACTIVITY_LOADER,{optional:true});readonly hasActivityLoader=!!this.activityLoader;
 readonly notificationComponent=signal<Type<unknown>|null>(null);
 private readonly communicationsLoader=inject(KOINON_COMMUNICATIONS_LOADER,{optional:true});
 readonly notificationActions={opened:()=>this.openAccount('notifications')};
 readonly commandsOpen=signal(false);
 private requestNewConversation=false;
 readonly commands=computed<KoinonCommand[]>(()=>{
  if(this.f.authRequired()||!this.f.context()?.subject)return [];
  const commands:KoinonCommand[]=[{id:'library',title:'Open Library',icon:'folder'}];
  if(this.hasChatLoader)commands.push({id:'chat',title:'Open Chat',icon:'chat'},{id:'new-chat',title:'New conversation',icon:'plus',disabled:this.assistant.running()||this.assistant.pending()});
  if(this.activityLoader)commands.push({id:'my-activity',title:'My activity',icon:'history'});
  if(this.canConfigure())commands.push({id:'activity',title:'View activity',icon:'history'},{id:'settings',title:'Open Settings',icon:'settings'});
  if(this.f.canUpload())commands.push({id:'upload',title:'Upload files',description:'Add knowledge to your Library',icon:'upload',disabled:this.f.pending()});
  if(this.showNavigation)commands.push({id:'profile',title:'Profile & preferences',icon:'users'},{id:'tokens',title:'API tokens',icon:'shield'},{id:'applications',title:'Authorized applications',icon:'link'});
  return commands.map(command=>({...command,title:this.i18n.text(command.title),description:command.description?this.i18n.text(command.description):undefined}));
 });
 @HostListener('keydown.escape',['$event']) dismissPendingDialog(event:Event){if(this.dialog()&&!this.overlayRef){event.preventDefault();event.stopPropagation();this.closeDialog();}}
 @HostListener('keydown',['$event']) commandShortcut(event:KeyboardEvent){
  if(event.isComposing||event.repeat||event.altKey||!(event.metaKey||event.ctrlKey)||event.key.toLowerCase()!=='k'||this.f.authRequired()||this.dialog()||this.tableLineage.target()||this.invitationToken)return;
  event.preventDefault();event.stopPropagation();this.openCommands();
 }
 openCommands(){if(this.f.context()?.subject&&!this.f.authRequired()&&!this.dialog()&&!this.tableLineage.target()&&!this.invitationToken)this.commandsOpen.set(true);}
 async runCommand(id:string){
  if(!this.commands().some(command=>command.id===id&&!command.disabled))return;
  this.commandsOpen.set(false);
  if(['library','chat','my-activity','activity','settings'].includes(id))await this.navigate(id as PrimaryDestination);
  else if(id==='new-chat'){if(this.destination()==='chat'&&this.chatComponent())this.assistant.newConversation();else{this.requestNewConversation=true;await this.navigate('chat');}}
  else if(id==='upload'){await this.navigate('library');if(this.f.canUpload()){this.openAdd();this.beginUpload();}}
  else if(id==='profile'||id==='tokens'||id==='applications')this.openAccount(id);
 }
 async openCommandResource(entry:CatalogEntry){if(entry.tenant_id===this.f.tenantId())await this.openChatResource(entry.id);}
 async commandSearch(query:string){await this.navigate('library');this.searchText.set(query);await this.search(query);}
 @Input()client?:KoinonClient;@Input()transport?:KoinonTransport|null;@Input()tenantId='';@Input()workspaceId='';@Input()projectId='';@Input()resourceId='';@Input()theme:'light'|'dark'='light';@Input({transform:booleanAttribute})showNavigation=true;@Input({transform:booleanAttribute})navigationCollapsed=false;@Input()accountSection:'profile'|'tokens'|'applications'|'notifications'|'notification-preferences'|null=null;@Output()accountSectionChange=new EventEmitter<'profile'|'tokens'|'applications'|'notifications'|'notification-preferences'|null>();@Input()view:PrimaryDestination='library';@Output()viewChange=new EventEmitter<PrimaryDestination>();@Output()navigationCollapsedChange=new EventEmitter<boolean>();@Input()branding:BrandingValues|null=null;@Output()brandingChange=new EventEmitter<BrandingValues>();@Input()brandBase='/assets/brand';@Input()managementBaseUrl='';@Input()invitationToken='';@Input()sharedConversationId='';@Output()sharedConversationDismissed=new EventEmitter<void>();
 @Output()invitationAccepted=new EventEmitter<Membership>();@Output()invitationDismissed=new EventEmitter<void>();
 readonly invitationComponent=signal<Type<unknown>|null>(null);readonly invitationError=signal('');private readonly invitationLoader=inject(KOINON_INVITATION_LOADER,{optional:true});readonly invitationActions={accepted:(membership:Membership)=>{void this.acceptInvitation(membership);},dismissed:()=>this.dismissInvitation()};
 @Output()selectionChange=new EventEmitter<CatalogEntry>();@Output()queryCompleted=new EventEmitter<QueryResponse>();@Output()citationSelected=new EventEmitter<Citation>();@Output()contextChange=new EventEmitter<KoinonScope>();@Output()authenticationRequired=new EventEmitter<void>();@Output()signOutRequested=new EventEmitter<void>();@Output()themeChange=new EventEmitter<'light'|'dark'>();
 readonly settingsComponent=signal<Type<unknown>|null>(null);private readonly settingsLoader=inject(KOINON_SETTINGS_LOADER,{optional:true});readonly hasSettingsLoader=!!this.settingsLoader;readonly settingsInitialSection=signal('providers');readonly requestedAgentId=signal('');readonly settingsActions={navigationCollapsed:()=>this.assistant.historyCollapsed(),toggleNavigation:()=>this.assistant.historyCollapsed.update(value=>!value),invitationBaseUrl:()=>this.managementBaseUrl,section:()=>this.settingsInitialSection(),chat:(id:string)=>{this.requestedAgentId.set(id);void this.navigate('chat');},addKnowledge:()=>{this.destination.set('library');this.openAdd();this.beginUpload();},resource:(id:string)=>this.openChatResource(id)};readonly chatComponent=signal<Type<unknown>|null>(null);private readonly chatLoader=inject(KOINON_CHAT_LOADER,{optional:true});readonly hasChatLoader=!!this.chatLoader;readonly chatActions={newConversation:()=>{const requested=this.requestNewConversation;this.requestNewConversation=false;return requested;},managementBaseUrl:()=>this.managementBaseUrl,avatar:()=>this.account.effectiveAvatar(),displayName:()=>this.displayName(),brandBase:()=>this.brandBase,assistantName:()=>this.brand.value().assistant_name,brandSymbol:()=>this.brandSymbol(),locale:()=>this.i18n.preferences().locale,agentId:()=>{const id=this.requestedAgentId();this.requestedAgentId.set('');return id;},setup:()=>{this.settingsInitialSection.set('agents');return this.navigate('settings');},citation:(citation:Citation)=>this.openCitation(citation),resource:(id:string)=>this.openChatResource(id)};
 readonly brand=inject(KoinonBranding);
 brandLogo(){return brandImage(this.brand.value(),this.theme,this.brandBase);}
 brandSymbol(){return brandSymbol(this.brand.value(),this.brandBase);}
 private applyBrand(){for(const [key,value] of Object.entries(brandStyles(this.brand.value(),this.theme)))this.host.nativeElement.style.setProperty(key,value);}
 private readonly font=inject(KoinonFontLoader);readonly account=inject(KoinonAccount);readonly i18n=inject(KoinonI18n);readonly f=inject(KoinonFacade);private readonly assistant=inject(KoinonAssistant);private readonly tasks=inject(PendingTasks);private dialogOverlay?:ReturnType<typeof createDialogOverlay>;private overlayLoading?:Promise<void>;private destroyed=false;private readonly vcr=inject(ViewContainerRef);private readonly host=inject<ElementRef<HTMLElement>>(ElementRef);private readonly injector=inject(Injector);private inspectorTrigger?:HTMLElement;private started=false;private overlayRef?:OverlayRef;private dialogTrigger?:HTMLElement;
 constructor(){effect(()=>{if(this.f.context()&&!this.f.initializing()&&!this.canConfigure()&&(this.destination()==='settings'||this.destination()==='activity'))void this.navigate('chat');});afterNextRender(()=>{this.communicationsLoader?.('trigger').then(component=>{if(!this.destroyed)this.notificationComponent.set(component);}).catch(()=>{/* Optional header loading must not block account access. */});});effect(()=>{const value=this.brand.value();this.applyBrand();void this.font.load(this.brand.assetBase(),value.font_family);this.brandingChange.emit(value);});effect(()=>{if(this.f.authRequired()){this.commandsOpen.set(false);this.overlayRef?.dispose();this.overlayRef=undefined;this.dialog.set(null);this.dialogError.set('');this.activeCitation=null;}});effect(()=>{const collapsed=this.assistant.historyCollapsed();if(collapsed!==this.navigationCollapsed){this.navigationCollapsed=collapsed;this.navigationCollapsedChange.emit(collapsed);}});}
 @ViewChild('dialogContent')private dialogContent!:TemplateRef<unknown>;
 private accountSectionControlled=false;readonly accountScreen=signal<'profile'|'tokens'|'applications'|'notifications'|'notification-preferences'|null>(null);readonly accountTab=signal<'profile'|'tokens'|'applications'>('profile');readonly destination=signal<PrimaryDestination>('library');readonly dialog=signal<Dialog|null>(null);readonly searchText=signal('');readonly searched=signal('');readonly dialogError=signal('');readonly uploadState=signal<'select'|'receiving'|'complete'>('select');readonly uploadedCount=signal(0);readonly uploadDestinationOpen=signal(false);readonly uploadedFiles=signal(new Set<File>());readonly uploadCurrentFile=signal<File|null>(null);readonly uploadFailedFile=signal<File|null>(null);readonly uploadFolderKinds:ResourceKind[]=['collection','corpus'];
 archiveQuery='';formName='';formDescription='';formKind:ResourceKind='workspace';formParent='';uploadMode='document';files:File[]=[];queryQuestion='';activeCitation:Citation|null=null;
 readonly allEntries=computed(()=>[...new Map([...(this.f.context()?.workspaces??[]),...this.f.entries()].filter(x=>x.tenant_id===this.f.tenantId()).map(x=>[x.id,x])).values()]);
 readonly trail=computed(()=>folderTrail(this.allEntries(),this.f.parentId()));readonly currentFolder=computed(()=>this.allEntries().find(x=>x.id===this.f.parentId()));readonly entries=computed(()=>this.f.libraryPage().items);readonly uploadFolders=computed(()=>this.allEntries().filter(x=>x.kind==='collection'||x.kind==='corpus'));readonly folderKind=computed(()=>nextFolderKind(this.currentFolder()));readonly allowedKinds=computed<{value:ResourceKind;label:string}[]>(()=>this.currentFolder()?.kind==='collection'||this.currentFolder()?.kind==='corpus'?[{value:'document',label:'Documents'},{value:'dataset',label:'Datasets'},{value:'source',label:'Sources awaiting files'}]:[]);
 readonly canConfigure=computed(()=>!!this.f.tenant()?.roles.includes('admin')&&this.f.tenantPermissions().has('members:write'));readonly roleLabel=computed(()=>this.f.tenant()?.roles.includes('admin')?'Administrator':this.f.tenant()?.roles.includes('operator')?'Operator':this.f.canWrite()?'Editor':'Member');readonly displayName=computed(()=>{if(this.account.organizationName()!==null)return this.account.organizationName()||this.i18n.text('Name unavailable');if(this.account.profile()?.display_name)return this.account.profile()!.display_name;const s=this.f.context()?.subject??'';return s.includes('@')&&!s.includes('|')?s.split('@')[0]:s&&!s.includes('|')&&!/^[a-f0-9-]{20,}$/i.test(s)?s:'Your account';});
 readonly queryColumns=computed(()=>Object.keys(this.f.queryResult()?.preview?.[0]??{}));readonly folderTitle=computed(()=>this.currentFolder()?.name??'Library');readonly folderDescription=computed(()=>this.currentFolder()?.description||(!this.f.parentId()?'A shared home for your team’s documents and data.':'Keep the knowledge your team needs together.'));
 ngOnInit(){this.brand.assetBase.set(this.brandBase);this.brand.setOverride(this.branding);if(this.sharedConversationId)void this.loadSharedConversation();if(this.invitationToken)void this.loadInvitation();this.started=true;if(this.client)this.f.bindClient(this.client,this.transport);this.tasks.run(()=>this.initialize());}
 ngOnChanges(changes:SimpleChanges){if(changes['branding'])this.brand.setOverride(this.branding);if(changes['theme'])this.applyBrand();if(changes['accountSection']){this.accountSectionControlled=true;this.accountScreen.set(this.accountSection);}else if(changes['view']&&!this.accountSectionControlled)this.accountScreen.set(null);if(changes['sharedConversationId']&&this.sharedConversationId)void this.loadSharedConversation();if(changes['navigationCollapsed'])this.assistant.historyCollapsed.set(this.navigationCollapsed);if(changes['view']&&this.started&&this.f.context())this.tasks.run(()=>this.navigate(this.view,true));if(changes['invitationToken']&&this.invitationToken)void this.loadInvitation();if(changes['brandBase']){this.brand.assetBase.set(this.brandBase);}if((changes['client']||changes['transport'])&&this.client)this.f.bindClient(this.client,this.transport);if(this.started&&['client','transport','tenantId','workspaceId','projectId','resourceId'].some(x=>changes[x]))this.tasks.run(()=>this.initialize());}
 ngOnDestroy(){this.destroyed=true;this.overlayRef?.dispose();this.dialogOverlay?.destroy();}
 retryConnection(){this.tasks.run(()=>this.initialize(this.f.context()?'':this.tenantId));}
 private async initialize(tenantId=this.tenantId){void this.brand.loadDefaults();await this.f.bootstrap(tenantId);if(this.f.tenantId()&&this.workspaceId)await this.f.setWorkspace(this.workspaceId);if(this.f.tenantId()&&this.projectId){this.f.projectId.set(this.projectId);this.f.parentId.set(this.projectId);await this.f.loadLibrary({page:1,q:'',kind:undefined,status:undefined,tag:undefined,format:undefined});}if(this.f.tenantId()&&this.resourceId){const entry=this.allEntries().find(x=>x.id===this.resourceId);if(entry)this.select(entry);else if(await this.f.loadResource(this.resourceId)){const loaded=this.f.selected();if(loaded)this.select(loaded);}}if(this.f.context()){void this.f.loadCapabilities();if(this.showNavigation)void this.account.load();}if(this.f.context()&&this.view!==this.destination())await this.navigate(this.view,true);}
 private focusMainHeading(){afterNextRender(()=>{const heading=this.host.nativeElement.shadowRoot?.querySelector<HTMLElement>('ffk-shell h1');if(heading){heading.tabIndex=-1;heading.focus();}},{injector:this.injector});}
 dismissInvitation(){this.invitationDismissed.emit();this.focusMainHeading();}
 async loadInvitation(){if(this.invitationComponent())return;this.invitationError.set('');if(!this.invitationLoader){this.invitationError.set('Invitation support is not enabled in this application.');return;}try{this.invitationComponent.set(await this.invitationLoader());}catch{this.invitationError.set('The invitation could not be opened. Try again.');}}
 private async acceptInvitation(membership:Membership){this.invitationAccepted.emit(membership);await this.f.bootstrap(membership.tenant_id);if(this.f.context()?.tenants.some(tenant=>tenant.id===membership.tenant_id)){if(membership.workspace_id&&this.f.context()?.workspaces.some(workspace=>workspace.id===membership.workspace_id&&workspace.tenant_id===membership.tenant_id))await this.f.setWorkspace(membership.workspace_id);this.destination.set('library');this.emitContext();this.focusMainHeading();}}
 emitContext(){this.contextChange.emit({tenantId:this.f.tenantId(),workspaceId:this.f.workspaceId()||undefined,projectId:this.f.projectId()||undefined,resourceId:this.f.selected()?.id});}
 async changeTenant(id:string){this.closeDialog();this.clearSearch();const navigation=this.navigate('library'),selection=this.f.selectTenant(id);this.emitContext();await Promise.all([navigation,selection]);}
 async navigate(destination:PrimaryDestination,fromHost=false){if((destination==='settings'||destination==='activity')&&!this.canConfigure()){destination='chat';fromHost=false;}const personal=!!this.accountScreen();if(personal&&!fromHost){if(!this.accountSectionControlled)this.accountScreen.set(null);this.accountSectionChange.emit(null);}this.tableLineage.close();if(this.sharedConversationId&&!fromHost)this.sharedConversationDismissed.emit();this.destination.set(destination);if(!fromHost&&(this.view!==destination||personal)){this.view=destination;this.viewChange.emit(destination);}if(destination!=='chat')this.f.selected.set(null);this.f.error.set('');this.f.notice.set('');if(destination==='chat'&&!this.chatComponent()&&this.chatLoader){try{this.chatComponent.set(await this.chatLoader());}catch{this.f.error.set('Chat could not be opened. Refresh this page and try again.');}}if(destination==='activity'||destination==='my-activity'){if(destination==='activity')await this.f.loadJobs();if(!this.activityComponent()&&this.activityLoader){try{this.activityComponent.set(await this.activityLoader());}catch{this.f.error.set('Activity could not be opened. Refresh this page and try again.');}}}if(destination==='settings'&&!this.settingsComponent()&&this.settingsLoader){try{this.settingsComponent.set(await this.settingsLoader());}catch{this.f.error.set('Settings could not be opened. Refresh this page and try again.');}}}
 async openFolder(id:string){this.clearSearch();this.f.selected.set(null);const entry=this.allEntries().find(x=>x.id===id);if(!id){this.f.workspaceId.set('');this.f.projectId.set('');this.f.parentId.set('');await this.f.loadLibrary({page:1,q:'',kind:undefined,status:undefined,tag:undefined,format:undefined});}else if(entry?.kind==='workspace'){await this.f.setWorkspace(entry.id);}else if(entry){this.f.workspaceId.set(entry.workspace_id??'');this.f.projectId.set(entry.kind==='project'?entry.id:entry.project_id??'');this.f.parentId.set(entry.id);await this.f.loadLibrary({page:1,q:'',kind:undefined,status:undefined,tag:undefined,format:undefined});}if(entry)this.selectionChange.emit(entry);this.emitContext();}
 async open(entry:CatalogEntry){if(isFolder(entry))await this.openFolder(entry.id);else this.select(entry);}
 select(entry:CatalogEntry){this.inspectorTrigger=this.host.nativeElement.shadowRoot?.activeElement as HTMLElement;this.f.selected.set(entry);this.selectionChange.emit(entry);this.emitContext();if(entry.kind==='dataset')void this.f.loadSchema(entry.id);}
 parentName(entry:CatalogEntry){if(this.f.libraryPage().items.some(row=>row.id===entry.id))return this.currentFolder()?.name||'Library';const parent=this.allEntries().find(x=>x.id===entry.parent_id);if(parent?.kind==='source')return this.allEntries().find(x=>x.id===parent.parent_id)?.name||parent.name;return parent?.name||'Library';}
 folderLabel(entry:CatalogEntry){return folderTrail(this.allEntries(),entry.id).map(x=>x.name).join(' / ');}
 async search(question:string){if(!question.trim())return;this.destination.set('library');this.f.selected.set(null);if(await this.f.search(question.trim(),false))this.searched.set(question.trim());}
 clearSearch(){this.searchText.set('');this.searched.set('');this.f.searchResult.set(null);}
 async openSearchResource(id:string){if(await this.f.loadResource(id)){const entry=this.f.selected();if(entry){this.selectionChange.emit(entry);this.emitContext();}}}
 showDialog(kind:Dialog){if(!this.dialog())this.dialogTrigger=this.host.nativeElement.shadowRoot?.activeElement as HTMLElement;this.dialog.set(kind);this.dialogError.set('');if(this.overlayRef)return;if(this.dialogOverlay){this.attachDialog();return;}if(this.overlayLoading)return;const complete=this.tasks.add();this.overlayLoading=import('./services/dialog-overlay').then(module=>{if(this.destroyed)return;this.dialogOverlay=module.createDialogOverlay(this.injector,this.host);this.attachDialog();}).catch(()=>{if(!this.destroyed&&this.dialog()){this.dialog.set(null);this.f.error.set('This panel could not be opened. Refresh this page and try again.');this.dialogTrigger?.focus();}}).finally(()=>{this.overlayLoading=undefined;complete();});}
 private attachDialog(){const kind=this.dialog();if(!kind||this.overlayRef||this.destroyed||this.f.authRequired())return;const ref=this.dialogOverlay!.open(kind==='tree',this.dialogContent,this.vcr);this.overlayRef=ref;ref.backdropClick().subscribe(()=>this.closeDialog());ref.keydownEvents().subscribe(event=>{if(event.key==='Escape'){event.preventDefault();this.closeDialog();}});}
 closeDialog(){if(this.uploadState()==='receiving')return;this.overlayRef?.dispose();this.overlayRef=undefined;this.dialog.set(null);this.dialogError.set('');this.dialogTrigger?.focus();}
 openAdd(){this.formName='';this.formDescription='';this.formParent=this.f.parentId();this.files=[];this.uploadedCount.set(0);this.uploadedFiles.set(new Set());this.uploadCurrentFile.set(null);this.uploadFailedFile.set(null);this.uploadState.set('select');this.showDialog('add');}
 beginCreate(){const kind=this.folderKind();if(!kind)return;this.formKind=kind;this.formName='';this.formDescription='';this.showDialog('create');}
 openEdit(){const entry=this.f.selected();if(!entry)return;this.formName=entry.name;this.formDescription=entry.description;this.showDialog('edit');}
 async save(){if(!this.formName.trim()){this.dialogError.set('Enter a name before continuing.');return;}const entry=this.f.selected();const done=this.dialog()==='edit'&&entry?await this.f.update(entry.id,{name:this.formName.trim(),description:this.formDescription.trim()}):await this.f.create({kind:this.formKind,name:this.formName.trim(),description:this.formDescription.trim(),parent_id:this.f.parentId()||null});if(done)this.closeDialog();else this.dialogError.set(this.f.error());}
 beginUpload(){this.formParent=this.uploadFolders().some(x=>x.id===this.f.parentId())?this.f.parentId():'';this.uploadDestinationOpen.set(!this.formParent);this.showDialog('upload');}
 captureFiles(event:Event){if(this.uploadState()==='receiving')return;this.files=Array.from((event.target as HTMLInputElement).files??[]);this.uploadedFiles.set(new Set());this.uploadedCount.set(0);this.uploadFailedFile.set(null);}
 dropFiles(event:DragEvent){event.preventDefault();if(!this.f.canUpload()||this.uploadState()==='receiving')return;this.openAdd();this.beginUpload();this.files=Array.from(event.dataTransfer?.files??[]);}
 captureDrop(event:DragEvent){event.preventDefault();if(this.uploadState()==='receiving')return;this.files=Array.from(event.dataTransfer?.files??[]);this.uploadedFiles.set(new Set());this.uploadedCount.set(0);this.uploadFailedFile.set(null);}
 async uploadRuntime(){return (await import('./services/library-upload')).libraryUpload(this,this.injector);}
 async upload(){await(await this.uploadRuntime()).start();}
 openUploadResult(){this.closeDialog();const selected=this.f.selected();if(selected){this.f.parentId.set(this.formParent);this.select(selected);}}
 async archive(){const entry=this.f.selected();if(entry&&isSystemManaged(entry)){this.dialogError.set(this.i18n.text('System spaces and folders cannot be archived.'));return;}if(entry&&await this.f.archive(entry))this.closeDialog();else this.dialogError.set(this.f.error());}
 readonly tableLineage=inject(KoinonTableLineage);
 async openTableHistory(table:{id:string;name:string}){
  const entry=this.f.selected();
  const datasetId=entry?.kind==='dataset'?entry.id:entry?.kind==='table'?entry.parent_id:null;
  if(!datasetId)return;
  const datasetName=entry?.kind==='dataset'?entry.name:this.allEntries().find(row=>row.id===datasetId)?.name||this.i18n.text('Dataset');
  this.closeDialog();
  await this.tableLineage.open({datasetId,datasetName,tableId:table.id,tableName:table.name});
 }
 async explore(){const entry=this.f.selected();if(!entry)return;this.queryQuestion='';this.f.queryResult.set(null);this.showDialog('query');await this.f.loadSchema(entry.id);}
 async runQuery(){const entry=this.f.selected();if(!entry||!this.queryQuestion.trim())return;if(await this.f.query(entry.id,this.queryQuestion.trim())){const result=this.f.queryResult();if(result)this.queryCompleted.emit(result);}}
 queryStatusTone(status:QueryResponse['execution_status']):'ready'|'attention'|'neutral'{
  if(status==='OK'||status==='REFINED_OK')return 'ready';
  if(status==='FAILED'||status==='REJECTED_BY_FIREWALL')return 'attention';
  return 'neutral';
 }
 queryStatusLabel(status:QueryResponse['execution_status']):string{
  if(status==='OK'||status==='REFINED_OK')return 'Query complete';
  if(status==='FAILED')return 'Query failed';
  if(status==='REJECTED_BY_FIREWALL')return 'Blocked by query policy';
  return 'Status unavailable';
 }
 async lineage(){this.showDialog('lineage');await this.f.loadLineage(this.f.selected()?.id);}
 nodeLabel(id:string){return this.f.lineage()?.nodes.find(x=>x.id===id)?.label||'Related resource';}
 openCitation(citation:Citation){this.activeCitation=citation;this.citationSelected.emit(citation);this.showDialog('citation');}
 async citationResource(id:string){if(await this.f.loadResource(id)){this.closeDialog();const entry=this.f.selected();if(entry)this.select(entry);}}
 readonly loadTreeChildren=(id:string,page=1)=>this.f.loadChildren(id,page);
 async openTreeFolder(id:string){this.closeDialog();await this.openFolder(id);}
 async openChatResource(id:string){if(await this.f.loadResource(id)){const entry=this.f.selected();await this.navigate('library');if(entry){if(isFolder(entry))await this.openFolder(entry.id);else this.select(entry);}}}
 async showArchived(){this.showDialog("archived");await this.f.loadArchived({page:1,q:""});}
 async restore(entry:CatalogEntry){if(await this.f.restore(entry))await this.f.loadArchived();}
 closeInspector(){const trigger=this.inspectorTrigger;this.f.selected.set(null);afterNextRender(()=>{if(trigger?.isConnected)trigger.focus();else this.host.nativeElement.shadowRoot?.querySelector<HTMLElement>('ffk-breadcrumb button[aria-current="page"]')?.focus();},{injector:this.injector});}
 chooseUploadFolder(id:string){const folder=this.allEntries().find(entry=>entry.id===id);if(!folder||!this.uploadFolderKinds.includes(folder.kind))return;this.formParent=id;this.uploadDestinationOpen.set(false);afterNextRender(()=>this.host.nativeElement.shadowRoot?.querySelector<HTMLElement>('#upload-files')?.focus(),{injector:this.injector});}
 uploadDestinationName(){const folder=this.allEntries().find(entry=>entry.id===this.formParent);return folder?this.folderLabel(folder):"Choose a folder";}
 remainingFiles(){return this.files.filter(file=>!this.uploadedFiles().has(file)).length;}
 openAccount(tab:'profile'|'tokens'|'applications'|'notifications'|'notification-preferences'){if(this.sharedConversationId)this.sharedConversationDismissed.emit();this.commandsOpen.set(false);this.tableLineage.close();if(this.dialog())this.closeDialog();if(!this.accountSectionControlled)this.accountScreen.set(tab);this.accountSectionChange.emit(tab);this.focusMainHeading();}
 readonly kind=friendlyKind;
}
