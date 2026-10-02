/** Inspectable formula-based pricing and cash-flow review workbook.
 * Credit paths are exported model inputs. Excel owns discounting, price, WAL and
 * note roll-forward checks. Borrower-model assumptions require a Python rerun.
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const ROOT=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const args=process.argv.slice(2);
const option=(name,defaultValue)=>{const i=args.indexOf(name);return i<0?defaultValue:args[i+1];};
const input=option('--input',path.join(ROOT,'output','platform_results.json'));
const output=option('--output',path.join(ROOT,'output','outputs','credit_research','cashflow_workbook.xlsx'));
const qaDir=path.join(ROOT,'output','qa','workbook');
const inputBytes=await fs.readFile(input);
const resultsSha=createHash('sha256').update(inputBytes).digest('hex');
const runStatus=JSON.parse(await fs.readFile(option('--run-status',path.join(path.dirname(input),'platform_run_status.json')),'utf8'));
if(runStatus.status!=='SUCCESS')throw new Error('Research run is not SUCCESS; refusing to export stale artifacts');
if(runStatus.results_sha256!==resultsSha)throw new Error('Results SHA-256 differs from the successful run record');
const p=JSON.parse(inputBytes.toString('utf8'));
if(runStatus.built_at!==p.generated_at)throw new Error('Results date differs from successful run version');
if(!p.platform?.valuation_date)throw new Error('An explicit cash-flow valuation date is required');
if(!p.platform||!p.scenarios?.length)throw new Error('Missing completed platform scenarios');
const num=(v,label)=>{if(typeof v!=='number'||!Number.isFinite(v))throw new Error(`Missing numeric ${label}`);return v;};
const cents=(v,label)=>num(v,label)/100;
const periodDate=value=>new Date(`${value}T00:00:00Z`);
const nName=t=>t.name||t.class;
const begin=t=>t.opening_balance_cents??t.initial_balance_cents;
const rowField=(r,key,alternate)=>r[key]??r[alternate];
const cases=p.scenarios;
const classes=cases[0].tranches.map(nName);
if(cases.some(s=>s.tranches.map(nName).join(',')!==classes.join(',')))throw new Error('Scenario classes must share the same ordering');
const maxMonths=Math.max(...cases.map(s=>s.pool_rows.length));
const raw=[];
for(const [si,s] of cases.entries())for(const [ti,t] of s.tranches.entries()){
  if(t.rows.length!==s.pool_rows.length)throw new Error(`${s.name} ${nName(t)} horizon differs from its collateral horizon`);
  if(t.rows.length<maxMonths&&rowField(t.rows.at(-1),'closing_balance_cents','note_end_cents')!==0)throw new Error(`${s.name} ${nName(t)} shorter horizon leaves unpaid principal; cannot treat it as economically closed`);
  for(const r of t.rows){raw.push([si+1,ti+1,num(r.month,'month'),r.distribution_date?periodDate(r.distribution_date):r.period||`Month ${r.month}`,cents(rowField(r,'opening_balance_cents','note_begin_cents'),'opening balance'),cents(rowField(r,'interest_paid_cents','interest_cents'),'interest paid'),cents(rowField(r,'principal_paid_cents','principal_cents'),'principal paid'),cents(rowField(r,'loss_cents','principal_loss_cents'),'principal loss'),cents(rowField(r,'closing_balance_cents','note_end_cents'),'closing balance'),cents(r.interest_arrears_cents??r.interest_shortfall_cents??r.arrears_cents??0,'interest arrears'),num(r.time_years??r.month/12,'elapsed years'),cents(r.contractual_closing_balance_cents??rowField(r,'closing_balance_cents','note_end_cents'),'contractual closing balance')]);}
}
const wb=Workbook.create();
const names=['Summary','Controls','Cashflow','Exported CF','Actuals','Loan tape','Sources','Forecast checks','Audit'];
const sheets=Object.fromEntries(names.map(n=>[n,wb.worksheets.add(n)]));
const NAVY='#102537',INK='#17334A',MUTED='#657582',LINE='#DDE3E4',TAN='#F4F1E8',BLUE='#2457AE',GREEN='#267346',AMBER='#FFF0C7';
const fmtMoney='#,##0.00;(#,##0.00);"-"';
const fmtPrice='0.00;(0.00);"-"';
for(const s of Object.values(sheets)){s.showGridLines=false;s.getRange('A1:S100').format.font={name:'Arial',size:10,color:INK};s.getRange('A1:S100').format.rowHeight=20;s.getRange('A:B').format.columnWidth=2.5;s.getRange('C:C').format.columnWidth=27;s.getRange('D:S').format.columnWidth=16;s.getRange('A1:S100').format.verticalAlignment='center';}
const title=(s,value)=>{s.getRange('C2').values=[[value]];s.getRange('C2').format.font={name:'Arial',size:16,bold:true,color:NAVY};s.getRange('C2:P2').format.borders={bottom:{style:'thin',color:LINE}};s.getRange('C2:P2').format.rowHeight=28;};
const header=(s,range,values)=>{s.getRange(range).values=[values];s.getRange(range).format={fill:NAVY,font:{name:'Arial',size:10,color:'#FFFFFF',bold:true},horizontalAlignment:'center',rowHeight:28,wrapText:true,borders:{insideVertical:{style:'thin',color:'#FFFFFF'}}};};
const values=(s,cell,data)=>s.getRange(cell).write(data);
const formula=(s,cell,value)=>{s.getRange(cell).formulas=[[value]];};
const sourceStyle=(s,range)=>{s.getRange(range).format.font.color=BLUE;s.getRange(range).setNumberFormat(fmtMoney);};
const caseDisplay=(s)=>{s.getRange('C4').values=[['Case selected:']];formula(s,'D4',"=Controls!D6");s.getRange('D4').format={font:{name:'Arial',size:10,color:GREEN,bold:true},borders:{preset:'outside',style:'dotted',color:LINE},horizontalAlignment:'center'};};

const controls=sheets.Controls;title(controls,'Pricing controls');controls.tabColor='#547084';
values(controls,'C35',[['Valuation date',periodDate(p.platform.valuation_date)],['Model build UTC',p.generated_at],['Verified results SHA-256',resultsSha]]);controls.getRange('D35').setNumberFormat('mm/dd/yyyy');controls.getRange('D36').setNumberFormat('yyyy-mm-dd hh:mm:ss');controls.getRange('C35:H37').format.font={name:'Arial',size:9,color:MUTED};
values(controls,'C5',[
 ['Scenario number',1],['Scenario selected',null],['Class number',classes.length],['Class selected',null],['Effective annual discount yield',cases[0].assumptions?.discount_rate??0.06],['Assumed purchase price / $100',100],['Yield sensitivity step',0.01],['Active modeled months',null]
]);
const caseNames=cases.map(s=>s.name);values(controls,'G5',[['Scenario number','Saved model scenario','Modeled months'],...cases.map((s,i)=>[i+1,s.name,s.pool_rows.length])]);
values(controls,'G13',[['Class number','Note class'],...classes.map((n,i)=>[i+1,n])]);
header(controls,'G5:I5',['Scenario number','Saved model scenario','Modeled months']);header(controls,'G13:H13',['Class number','Note class']);
formula(controls,'D6',`=INDEX(H6:H${5+cases.length},D5)`);formula(controls,'D8',`=INDEX(H14:H${13+classes.length},D7)`);
formula(controls,'D12',`=INDEX(I6:I${5+cases.length},D5)`);
for(const row of [5,7,9,10,11])controls.getRange(`D${row}`).format={fill:AMBER,font:{name:'Arial',size:10,color:BLUE}};
controls.getRange('D9').setNumberFormat('0.00%');controls.getRange('D11').setNumberFormat('0.00%');controls.getRange('D10').setNumberFormat(fmtPrice);
controls.dataValidations.add({range:'D5',rule:{type:'whole',operator:'between',formula1:1,formula2:cases.length}});
controls.dataValidations.add({range:'D7',rule:{type:'whole',operator:'between',formula1:1,formula2:classes.length}});
controls.dataValidations.add({range:'D9',rule:{type:'decimal',operator:'between',formula1:0,formula2:1}});
controls.dataValidations.add({range:'D10',rule:{type:'decimal',operator:'between',formula1:0,formula2:200}});
controls.dataValidations.add({range:'D11',rule:{type:'decimal',operator:'between',formula1:0,formula2:0.5}});
values(controls,'C25',[
 ['Yellow cells are editable. Numeric inputs are blue.'],
 ['Scenario selection loads a saved Python credit path.'],
 ['Yield and assumed price recalculate the Excel valuation.'],
 ['Default, prepayment and recovery assumptions require a Python rerun.'],
 ['No independently sourced market quote is included.'],
 ['WAL uses actual elapsed days / 365.25 when supplied by the model.'],
 ['WAL is unavailable after principal loss or incomplete repayment.'],
 ['Repaid-principal WAL averages the timing of principal actually paid.'],
 ['Economic impairment is noncash. The contractual unpaid claim is preserved.']
]);controls.getRange('C25:H31').format.font={name:'Arial',size:10,color:MUTED};controls.getRange('C25:H31').format.wrapText=false;

const exported=sheets['Exported CF'];title(exported,'Python model cash-flow inputs (USD)');caseDisplay(exported);
values(exported,'C6',[[`Saved scenarios: ${caseNames.join(', ')}. These inputs change only when the Python model is rerun.`]]);
header(exported,'C8:N8',['Scenario ID','Class ID','Month','Period','Opening note','Interest paid','Principal paid','Principal loss','Economic closing','Interest arrears','Elapsed years','Contractual closing']);
values(exported,'C9',raw);exported.getRange(`C9:N${8+raw.length}`).format={font:{name:'Arial',size:10,color:INK},rowHeight:20};exported.getRange(`F9:F${8+raw.length}`).setNumberFormat('mm/dd/yy');sourceStyle(exported,`G9:L${8+raw.length}`);exported.getRange(`M9:M${8+raw.length}`).setNumberFormat('0.000000');sourceStyle(exported,`N9:N${8+raw.length}`);exported.getRange('C:C').format.columnWidth=12;exported.getRange('D:F').format.columnWidth=13;exported.freezePanes.freezeRows(8);exported.freezePanes.freezeColumns(6);
const last=raw.length+8;
const sources=sheets.Sources;title(sources,'Original source provenance');
header(sources,'C5:H5',['Filing / role','Period','Accession','SHA-256','URL','Archive path']);
const sourceRows=(p.source_provenance||[]).map(s=>[s.title||s.role||s.kind||'SEC filing',s.period||'',s.accession||'',s.sha256||'Unavailable',s.url||'',s.path||'']);
if(!sourceRows.length)throw new Error('Source provenance is required for workbook');values(sources,'C6',sourceRows);sources.getRange('C:C').format.columnWidth=34;sources.getRange('D:E').format.columnWidth=22;sources.getRange('F:H').format.columnWidth=78;sources.getRange(`C6:H${5+sourceRows.length}`).format.font={name:'Arial',size:9,color:INK};sources.freezePanes.freezeRows(5);

const forecast=sheets['Forecast checks'];title(forecast,'Withheld servicing cash: forecast diagnostics');
const cashValidation=p.forecast_validation?.cashflow_validation;
if(!cashValidation?.scores?.length)throw new Error('Withheld cash-flow validation scores required');
header(forecast,'C5:I5',['Deal','Cash quantity','Months','Baseline MAE','Model MAE','Model minus baseline','MAE improvement']);
const forecastRows=cashValidation.scores.map(r=>[r.deal_id,r.quantity.replaceAll('_',' '),r.months,num(r.baseline_mae_cents,'baseline cash MAE')/100,num(r.model_mae_cents,'model cash MAE')/100,null,null]);values(forecast,'C6',forecastRows);
for(let i=0;i<forecastRows.length;i++){const r=6+i;formula(forecast,`H${r}`,`=G${r}-F${r}`);formula(forecast,`I${r}`,`=IF(F${r}>0,(F${r}-G${r})/F${r},"n.a.")`);}
forecast.getRange('C:C').format.columnWidth=21;forecast.getRange('D:D').format.columnWidth=27;forecast.getRange('E:E').format.columnWidth=9;forecast.getRange('F:H').format.columnWidth=22;forecast.getRange('I:I').format.columnWidth=19;forecast.getRange(`F6:G${5+forecastRows.length}`).format.font.color=GREEN;forecast.getRange(`F6:H${5+forecastRows.length}`).setNumberFormat('#,##0.00;(#,##0.00);0.00');forecast.getRange(`I6:I${5+forecastRows.length}`).setNumberFormat('0.0%;(0.0%);0.0%');forecast.getRange(`H6:H${5+forecastRows.length}`).conditionalFormats.addCustom('H6>0',{fill:'#FCE6DF',font:{color:'#B64832'}});
values(forecast,'C17',[
 ['USD MAE versus future certificate cash; lower is better.'],
 ['Positive improvement means lower model error. Negative means worse.'],
 ['The fitted model improves unseen-deal defaults and interest,'],
 ['but materially worsens principal collections and pool runoff.'],
 ['Scenarios remain illustrative assumptions, not validated investment forecasts.'],
 ['MAE inputs are exported Python diagnostics; Excel calculates comparisons.'],
 ['The borrower event target is first-observed default disclosure.'],
 ['Effective default dates can precede first public observation.'],
 ['Source-taxonomy differences remain included in measured cash error.'],
 ['Monthly predictions, public origin dates and assumptions: platform_results.json.']
]);forecast.getRange('C17:I26').format.font={name:'Arial',size:10,color:MUTED};forecast.freezePanes.freezeRows(5);
if(p.supplemental_validation){values(forecast,'C28',[['Supplemental after-inspection study: see the dashboard Validation section.']]);forecast.getRange('C28:I28').format.font={name:'Arial',size:10,color:MUTED};}

const actuals=sheets.Actuals;title(actuals,'Servicer-reported values (USD)');
header(actuals,'C5:F5',['Collection period','Reported quantity','Reported amount','Original certificate URL']);
const actualRows=[];const historical=[];
for(const rec of p.certificates||[])for(const cmp of rec.replay_comparison||[]){const reported=cmp.reported_cents;const calculated=cmp.computed_cents;if(typeof reported==='number'&&typeof calculated==='number'){const period=periodDate(rec.collection_period_end);actualRows.push([period,cmp.name,reported/100,rec.source_url]);historical.push({period,name:cmp.name,calculated:calculated/100,sourceRow:actualRows.length+5});}}
if(!actualRows.length)throw new Error('Reported certificate amounts required for workbook');values(actuals,'C6',actualRows);actuals.getRange(`C6:C${5+actualRows.length}`).setNumberFormat('mm/dd/yy');sourceStyle(actuals,`E6:E${5+actualRows.length}`);actuals.getRange('C:C').format.columnWidth=18;actuals.getRange('D:D').format.columnWidth=34;actuals.getRange('F:F').format.columnWidth=92;actuals.freezePanes.freezeRows(5);
const loanTape=sheets['Loan tape'];title(loanTape,'Loan-tape aggregate source controls');
header(loanTape,'C5:I5',['Deal','Period','Quantity','Loan tape','Certificate','Unit','Source definition']);
const loanRows=[];
for(const rec of p.loan_tape_reconciliation?.comparisons||[])for(const check of rec.checks||[]){const scale=check.units==='cents'?100:1;loanRows.push([rec.deal_id,periodDate(rec.period_end),check.check,num(check.observed,'loan tape aggregate')/scale,num(check.reported,'certificate aggregate')/scale,scale===100?'USD':'loans',check.explanation||'']);}
if(loanRows.length){values(loanTape,'C6',loanRows);loanTape.getRange(`C6:I${5+loanRows.length}`).format={font:{name:'Arial',size:10,color:INK},rowHeight:30};loanTape.getRange(`D6:D${5+loanRows.length}`).setNumberFormat('mm/dd/yy');sourceStyle(loanTape,`F6:G${5+loanRows.length}`);for(let i=0;i<loanRows.length;i++)if(loanRows[i][5]==='loans')loanTape.getRange(`F${6+i}:G${6+i}`).setNumberFormat('#,##0');loanTape.getRange(`I6:I${5+loanRows.length}`).format.wrapText=true;loanTape.getRange('C:D').format.columnWidth=18;loanTape.getRange('E:E').format.columnWidth=30;loanTape.getRange('H:H').format.columnWidth=9;loanTape.getRange('I:I').format.columnWidth=95;loanTape.getRange(`C6:I${5+loanRows.length}`).format.autofitRows();loanTape.freezePanes.freezeRows(5);}
else loanTape.getRange('C6').values=[['No loan-tape aggregate controls supplied.']];

const cash=sheets.Cashflow;title(cash,'Active note cash flows and pricing (USD)');cash.getRange('C4').values=[['Case selected:']];formula(cash,'E4','=Controls!D6');cash.getRange('E4').format={font:{name:'Arial',size:10,color:GREEN,bold:true},borders:{preset:'outside',style:'dotted',color:LINE},horizontalAlignment:'center'};cash.getRange('G4').values=[['Class selected:']];formula(cash,'H4','=Controls!D8');cash.getRange('H4').format.font.color=GREEN;
header(cash,'C7:T7',['Month','Period','Opening','Interest','Principal','Loss','Closing','Interest arrears','Cash paid','Discount factor','Present value','Time-weighted principal','Expected closing','Difference','PV lower yield','PV higher yield','Source rows','Elapsed years']);
const cashRows=[];
const longestCase=cases.find(s=>s.pool_rows.length===maxMonths);
for(let i=0;i<maxMonths;i++){const row=longestCase.pool_rows[i];cashRows.push([i+1,row?.period||row?.distribution_date?.slice(0,7)||`Month ${i+1}`]);}values(cash,'C8',cashRows);
const rawCols={E:'G',F:'H',G:'I',H:'J',I:'K',J:'L'};
for(let r=8;r<8+maxMonths;r++){
  const count=`COUNTIFS('Exported CF'!$C$9:$C$${last},Controls!$D$5,'Exported CF'!$D$9:$D$${last},Controls!$D$7,'Exported CF'!$E$9:$E$${last},$C${r})`;
  formula(cash,`S${r}`,`=${count}`);
  for(const [column,rawCol] of Object.entries(rawCols))formula(cash,`${column}${r}`,`=IF(C${r}>Controls!$D$12,0,IF(S${r}=1,SUMIFS('Exported CF'!$${rawCol}$9:$${rawCol}$${last},'Exported CF'!$C$9:$C$${last},Controls!$D$5,'Exported CF'!$D$9:$D$${last},Controls!$D$7,'Exported CF'!$E$9:$E$${last},$C${r}),NA()))`);
  formula(cash,`T${r}`,`=IF(C${r}>Controls!$D$12,0,IF(S${r}=1,SUMIFS('Exported CF'!$M$9:$M$${last},'Exported CF'!$C$9:$C$${last},Controls!$D$5,'Exported CF'!$D$9:$D$${last},Controls!$D$7,'Exported CF'!$E$9:$E$${last},$C${r}),NA()))`);
  formula(cash,`K${r}`,`=F${r}+G${r}`);
  formula(cash,`L${r}`,`=1/(1+Controls!$D$9)^T${r}`);
  formula(cash,`M${r}`,`=K${r}*L${r}`);
  formula(cash,`N${r}`,`=G${r}*T${r}`);
  formula(cash,`O${r}`,`=E${r}-G${r}-H${r}`);
  formula(cash,`P${r}`,`=O${r}-I${r}`);
  formula(cash,`Q${r}`,`=K${r}/(1+MAX(0,Controls!$D$9-Controls!$D$11))^T${r}`);
  formula(cash,`R${r}`,`=K${r}/(1+Controls!$D$9+Controls!$D$11)^T${r}`);
}
cash.getRange(`E8:J${7+maxMonths}`).format.font.color=GREEN;cash.getRange(`K8:R${7+maxMonths}`).format.font.color='#000000';cash.getRange(`E8:K${7+maxMonths}`).setNumberFormat(fmtMoney);cash.getRange(`M8:R${7+maxMonths}`).setNumberFormat(fmtMoney);cash.getRange(`P8:P${7+maxMonths}`).setNumberFormat('#,##0.00;(#,##0.00);0.00');cash.getRange(`L8:L${7+maxMonths}`).setNumberFormat('0.000000');cash.getRange(`T8:T${7+maxMonths}`).setNumberFormat('0.000000');cash.getRange('T:T').format.columnWidth=13;cash.getRange('C:C').format.columnWidth=9;cash.getRange('D:D').format.columnWidth=14;cash.getRange('N:N').format.columnWidth=23;cash.freezePanes.freezeRows(7);cash.freezePanes.freezeColumns(4);
const cashLast=maxMonths+7;
const sum={};for(const col of ['F','G','H','J','K','M','N','Q','R'])sum[col]=`SUM(Cashflow!${col}8:${col}${cashLast})`;
const summary=sheets.Summary;title(summary,p.platform.deal_name||'CarMax Auto Owner Trust 2025-2');summary.tabColor=NAVY;caseDisplay(summary);summary.getRange('F4').values=[['Class selected:']];formula(summary,'G4','=Controls!D8');summary.getRange('G4').format.font.color=GREEN;
values(summary,'C6',[['Pricing from forecast cash flows (USD)'],['Opening principal'],['Paid principal'],['Principal loss'],['Economic principal at horizon'],['Interest paid'],['Unpaid interest at horizon'],['WAL (years)'],['Discounted cash-flow value'],['Model value / $100'],['Assumed purchase price / $100'],['Value minus purchase assumption / $100'],['Repaid-principal WAL (years)']]);
formula(summary,'D7','=Cashflow!E8');formula(summary,'D8',`=${sum.G}`);formula(summary,'D9',`=${sum.H}`);formula(summary,'D10',`=Cashflow!I${cashLast}`);formula(summary,'D11',`=${sum.F}`);formula(summary,'D12',`=INDEX(Cashflow!J8:J${cashLast},Controls!D12)`);formula(summary,'D13',`=IF(OR(D7=0,D9>0,D10>0),"n.a.",${sum.N}/D8)`);formula(summary,'D14',`=${sum.M}`);formula(summary,'D15','=IF(D7=0,"n.a.",100*D14/D7)');formula(summary,'D16','=Controls!D10');formula(summary,'D17','=IF(D7=0,"n.a.",D15-D16)');formula(summary,'D18',`=IF(D8=0,"n.a.",${sum.N}/D8)`);summary.getRange('D18').setNumberFormat('0.00');values(summary,'C19',[['Contractual principal remaining']]);formula(summary,'D19',`=SUMIFS('Exported CF'!$N$9:$N$${last},'Exported CF'!$C$9:$C$${last},Controls!$D$5,'Exported CF'!$D$9:$D$${last},Controls!$D$7,'Exported CF'!$E$9:$E$${last},Controls!$D$12)`);summary.getRange('D19').setNumberFormat(fmtMoney);
summary.getRange('D7:D14').setNumberFormat(fmtMoney);summary.getRange('D13').setNumberFormat('0.00');summary.getRange('D15:D17').setNumberFormat(fmtPrice);summary.getRange('C6:D6').format={fill:TAN,font:{name:'Arial',size:10,bold:true,color:NAVY},rowHeight:25};summary.getRange('C:C').format.columnWidth=45;summary.getRange('D:D').format.columnWidth=20;
header(summary,'C20:F20',['Yield case','Effective annual yield','Value / $100','Value gap / $100']);
values(summary,'C21',[['Lower yield'],['Selected yield'],['Higher yield']]);
formula(summary,'D21','=MAX(0,Controls!D9-Controls!D11)');formula(summary,'D22','=Controls!D9');formula(summary,'D23','=Controls!D9+Controls!D11');
formula(summary,'E21',`=IF(D7=0,"n.a.",100*${sum.Q}/D7)`);formula(summary,'E22','=D15');formula(summary,'E23',`=IF(D7=0,"n.a.",100*${sum.R}/D7)`);
for(let r=21;r<=23;r++)formula(summary,`F${r}`,`=IF($D$7=0,"n.a.",E${r}-$D$16)`);summary.getRange('D21:D23').setNumberFormat('0.00%');summary.getRange('E21:F23').setNumberFormat(fmtPrice);
values(summary,'C27',[
 ['Change the scenario, class, yield and price in Controls.'],
 ['Scenario cash flows are saved Python calculations.'],
 ['Credit assumptions require rerunning the research pipeline.'],
 ['Unresolved source exceptions remain. See Loan tape, Sources and Audit.'],
 [`Observed through ${p.platform.as_of||'unavailable'}. Dollar amounts are unscaled.`]
]);summary.getRange('C27:H31').format.font={name:'Arial',size:10,color:MUTED};values(summary,'C33',[[`Valuation date: ${p.platform.valuation_date}. See Forecast checks for mixed holdout results.`]]);summary.getRange('C33:H33').format.font={name:'Arial',size:10,color:MUTED};
const chart=summary.charts.add('line',[cash.getRange(`D7:D${cashLast}`),cash.getRange(`I7:I${cashLast}`)]);chart.title='Economic note principal (USD)';chart.titleTextStyle.typeface='Arial';chart.titleTextStyle.fontSize=12;chart.hasLegend=false;chart.xAxis={axisType:'textAxis',tickLabelInterval:6,textStyle:{typeface:'Arial',fontSize:9}};chart.yAxis={numberFormatCode:'$0.0,,"M"',numberFormatSourceLinked:false,textStyle:{typeface:'Arial',fontSize:9}};chart.series.items[0].line={fill:NAVY,style:'solid',width:2};chart.setPosition('H6','P23');

const audit=sheets.Audit;title(audit,'Independent financial reconciliation (USD)');caseDisplay(audit);
header(audit,'C7:F7',['Review item','Calculated','Observed / control','Difference']);
values(audit,'C8',[['Note opening equals paid principal + losses + closing'],['Maximum monthly roll-forward residual'],['Total modeled source rows'],['Maximum source rows per month']]);
formula(audit,'D8',`=${sum.G}+${sum.H}+Cashflow!I${cashLast}`);formula(audit,'E8','=Cashflow!E8');formula(audit,'F8','=D8-E8');formula(audit,'D9',`=MAX(Cashflow!P8:P${cashLast})`);formula(audit,'E9',`=MIN(Cashflow!P8:P${cashLast})`);formula(audit,'F9','=MAX(ABS(D9),ABS(E9))');formula(audit,'D10',`=SUM(Cashflow!S8:S${cashLast})`);formula(audit,'E10','=Controls!D12');formula(audit,'F10','=D10-E10');formula(audit,'D11',`=MAX(Cashflow!S8:S${cashLast})`);audit.getRange('E11').values=[[1]];formula(audit,'F11','=D11-E11');
header(audit,'C14:G14',['Period','Replayed quantity','Calculated replay','Servicer-reported','Difference']);
values(audit,'C15',historical.map(h=>[h.period,h.name,h.calculated,null,null]));
audit.getRange(`C15:C${14+historical.length}`).setNumberFormat('mm/dd/yy');
for(let i=0;i<historical.length;i++){const r=i+15;formula(audit,`F${r}`,`=Actuals!E${historical[i].sourceRow}`);formula(audit,`G${r}`,`=E${r}-F${r}`);}
audit.getRange('C:C').format.columnWidth=53;audit.getRange('D:D').format.columnWidth=35;audit.getRange(`E15:G${14+historical.length}`).setNumberFormat(fmtMoney);audit.getRange(`G15:G${14+historical.length}`).setNumberFormat('#,##0.00;(#,##0.00);0.00');audit.getRange('D8:F11').setNumberFormat('0.00');audit.getRange('F8:F11').conditionalFormats.addCustom('ABS(F8)>0.01',{fill:'#FCE6DF',font:{color:'#B64832',bold:true}});audit.getRange(`G15:G${14+historical.length}`).conditionalFormats.addCustom('ABS(G15)>0.01',{fill:'#FCE6DF',font:{color:'#B64832',bold:true}});audit.freezePanes.freezeRows(14);
if(loanRows.length){const start=historical.length+18;header(audit,`C${start}:I${start}`,['Period','Deal','Quantity','Loan tape','Certificate','Difference','Unit']);const loanAuditRows=loanRows.map(row=>[row[1],row[0],row[2],null,null,null,row[5]]);values(audit,`C${start+1}`,loanAuditRows);audit.getRange(`C${start+1}:C${start+loanRows.length}`).setNumberFormat('mm/dd/yy');for(let i=0;i<loanRows.length;i++){const r=start+1+i;formula(audit,`F${r}`,`='Loan tape'!F${6+i}`);formula(audit,`G${r}`,`='Loan tape'!G${6+i}`);formula(audit,`H${r}`,`=F${r}-G${r}`);if(loanRows[i][5]==='loans')audit.getRange(`F${r}:H${r}`).setNumberFormat('#,##0');}audit.getRange(`F${start+1}:H${start+loanRows.length}`).setNumberFormat('#,##0.00;(#,##0.00);0.00');audit.getRange(`H${start+1}:H${start+loanRows.length}`).conditionalFormats.addCustom(`ABS(H${start+1})>0.001`,{fill:'#FCE6DF',font:{color:'#B64832',bold:true}});for(let i=0;i<loanRows.length;i++)if(loanRows[i][5]==='loans')audit.getRange(`F${start+1+i}:H${start+1+i}`).setNumberFormat('#,##0');audit.getRange('E:E').format.columnWidth=32;}

await fs.mkdir(path.dirname(output),{recursive:true});await fs.mkdir(qaDir,{recursive:true});wb.recalculate();
const independent=(scenario,tranche)=>{
  const yieldRate=controls.getRange('D9').values[0][0];
  const pv=tranche.rows.reduce((total,r)=>total+(rowField(r,'interest_paid_cents','interest_cents')+rowField(r,'principal_paid_cents','principal_cents'))/100/(1+yieldRate)**(r.time_years??r.month/12),0);
  if(Math.abs(summary.getRange('D14').values[0][0]-pv)>0.001)throw new Error(`${scenario.name} ${nName(tranche)}: spreadsheet PV differs from independent cash-flow calculation`);
  const principal=tranche.rows.reduce((total,r)=>total+rowField(r,'principal_paid_cents','principal_cents'),0);
  const weighted=tranche.rows.reduce((total,r)=>total+rowField(r,'principal_paid_cents','principal_cents')*(r.time_years??r.month/12),0);
  const repaidWal=principal>0?weighted/principal:'n.a.';
  const actualWal=summary.getRange('D18').values[0][0];
  if(typeof repaidWal==='number'?Math.abs(actualWal-repaidWal)>1e-9:actualWal!==repaidWal)throw new Error('Spreadsheet repaid-principal WAL differs from independent calculation');
  const arrears=tranche.rows.at(-1).interest_arrears_cents??tranche.rows.at(-1).interest_shortfall_cents??tranche.rows.at(-1).arrears_cents??0;
  if(Math.abs(summary.getRange('D12').values[0][0]-arrears/100)>0.001)throw new Error('Unpaid interest is not the terminal arrears balance');
  const claim=tranche.rows.at(-1).contractual_closing_balance_cents??rowField(tranche.rows.at(-1),'closing_balance_cents','note_end_cents');if(Math.abs(summary.getRange('D19').values[0][0]-claim/100)>0.001)throw new Error('Contractual principal claim does not match terminal source row');
};
independent(cases[0],cases[0].tranches.at(-1));
// Formula/input changes must affect the same build, then restore delivery state.
const baselinePV=num(summary.getRange('D14').values[0][0],'baseline PV');const baselineWal=summary.getRange('D13').values[0][0];const oldYield=controls.getRange('D9').values[0][0];controls.getRange('D9').values=[[oldYield+0.01]];wb.recalculate();const higherYieldPV=num(summary.getRange('D14').values[0][0],'higher-yield PV');if(baselinePV>0&&higherYieldPV>=baselinePV)throw new Error('Yield sensitivity did not reduce cash-flow PV');controls.getRange('D9').values=[[oldYield]];const oldPrice=controls.getRange('D10').values[0][0];const oldGap=summary.getRange('D17').values[0][0];controls.getRange('D10').values=[[oldPrice+1]];wb.recalculate();if(typeof oldGap==='number'&&Math.abs(summary.getRange('D17').values[0][0]-(oldGap-1))>1e-8)throw new Error('Purchase-price change did not update valuation gap');controls.getRange('D10').values=[[oldPrice]];
if(cases.length>1){controls.getRange('D5').values=[[cases.length]];wb.recalculate();if(summary.getRange('D4').values[0][0]!==cases.at(-1).name)throw new Error('Scenario selector did not update');independent(cases.at(-1),cases.at(-1).tranches.at(-1));controls.getRange('D5').values=[[1]];}
controls.getRange('D7').values=[[1]];wb.recalculate();independent(cases[0],cases[0].tranches[0]);if(begin(cases[0].tranches[0])===0&&summary.getRange('D15').values[0][0]!=='n.a.')throw new Error('Retired note price is not unavailable');controls.getRange('D7').values=[[classes.length]];
wb.recalculate();if(summary.getRange('D13').values[0][0]!==baselineWal)throw new Error('Restored inputs changed WAL');
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},summary:'Final formula error scan',maxChars:4000});
const overview=await wb.inspect({kind:'table',range:'Summary!C4:F23',include:'values,formulas',tableMaxRows:20,tableMaxCols:4,maxChars:4500});
await fs.writeFile(path.join(qaDir,'inspection.ndjson'),errors.ndjson+'\n'+overview.ndjson);
if(/"value":"#/.test(errors.ndjson))throw new Error('Unexpected formula error; inspect output/qa/workbook/inspection.ndjson');
for(const [name,range] of [['Summary','C2:P33'],['Controls','C2:I37'],['Cashflow','C2:T17'],['Exported CF','C2:N18'],['Actuals','C2:F17'],['Loan tape','C2:I15'],['Sources','C2:H15'],['Forecast checks','C2:I28'],['Audit','C2:G24']]){const blob=await wb.render({sheetName:name,range,scale:1,format:'png'});await fs.writeFile(path.join(qaDir,name.replaceAll(' ','_')+'.png'),new Uint8Array(await blob.arrayBuffer()));}
if(loanRows.length){const start=historical.length+18;const blob=await wb.render({sheetName:'Audit',range:`C${start}:I${Math.min(start+12,start+loanRows.length)}`,scale:1,format:'png'});await fs.writeFile(path.join(qaDir,'Audit_loan_controls.png'),new Uint8Array(await blob.arrayBuffer()));}
const file=await SpreadsheetFile.exportXlsx(wb);await file.save(output);
await fs.writeFile(path.join(qaDir,'verification.json'),JSON.stringify({input:path.relative(ROOT,input),results_sha256:resultsSha,generated_at:p.generated_at,valuation_date:p.platform.valuation_date,output_sha256:createHash('sha256').update(await fs.readFile(output)).digest('hex'),run_status:'SUCCESS',independent_pv_and_repaid_wal_verified:true,terminal_arrears_verified:true,yield_change_reduced_pv:true,price_change_recalculated_gap:true,scenario_selector_verified:cases.length>1,retired_class_verified:begin(cases[0].tranches[0])===0,baseline_pv_usd:baselinePV,baseline_wal_years:baselineWal,sheets:names,output},null,2));
console.log(`Workbook exported: ${output}`);console.log(overview.ndjson);
