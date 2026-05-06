%% 第二问
clear; clc; close all;

% 设置学术全局字体
set(groot, 'defaultAxesFontName', 'Cambria');
set(groot, 'defaultTextFontName', '华文中宋');

% 加载数据
excelPath = '附件：校园圈抽样数据.xlsx';

friendTable = readtable(excelPath, 'Sheet', '好友关系表');
userTable   = readtable(excelPath, 'Sheet', '用户属性表');
behavTable  = readtable(excelPath, 'Sheet', '行为数据表');

disp('Data loaded successfully');

% 绘图
G = graph(friendTable{:,1}, friendTable{:,2});

% 定位S11
s11_id = 'S11';
s11_idx = find(string(G.Nodes.Name) == s11_id);

currentFriends = neighbors(G, s11_idx);
currentFriendIDs = string(G.Nodes.Name(currentFriends));

disp(['S11 currently has ' num2str(length(currentFriends)) ' friends']);

% 重命名
userTable.Properties.VariableNames{1} = 'studentID';
userTable.Properties.VariableNames{2} = 'grade';
userTable.Properties.VariableNames{3} = 'majorCategory';
userTable.Properties.VariableNames{4} = 'major';
userTable.Properties.VariableNames{5} = 'clubs';
userTable.Properties.VariableNames{6} = 'class';

behavTable.Properties.VariableNames{1} = 'studentID';
behavTable.Properties.VariableNames{5} = 'techScore';
behavTable.Properties.VariableNames{6} = 'cultureScore';
behavTable.Properties.VariableNames{7} = 'activePeriod';

% 计算
allUsers = string(userTable.studentID);
nonFriends = setdiff(allUsers, [s11_id; currentFriendIDs]);

scores = zeros(length(nonFriends),1);
reasons = cell(length(nonFriends),1);

s11_row = userTable(strcmp(string(userTable.studentID), s11_id), :);
s11_behav = behavTable(strcmp(string(behavTable.studentID), s11_id), :);

for i = 1:length(nonFriends)
    cand_id = nonFriends(i);
    cand_row = userTable(strcmp(string(userTable.studentID), cand_id), :);
    cand_behav = behavTable(strcmp(string(behavTable.studentID), cand_id), :);
    
    cand_idx = find(string(G.Nodes.Name) == cand_id);
    common_friends = length(intersect(currentFriends, neighbors(G, cand_idx)));
    
    attr_score = 0;
    if strcmp(s11_row.grade{1}, cand_row.grade{1}), attr_score = attr_score + 2; end
    if strcmp(s11_row.majorCategory{1}, cand_row.majorCategory{1}), attr_score = attr_score + 3; end
    if contains(char(s11_row.clubs{1}), char(cand_row.clubs{1})), attr_score = attr_score + 4; end
    if contains(char(s11_row.class{1}), char(cand_row.class{1})), attr_score = attr_score + 2; end
    
    behav_score = 0;
    if strcmp(s11_behav.activePeriod{1}, cand_behav.activePeriod{1}), behav_score = behav_score + 3; end
    behav_score = behav_score + (10 - abs(s11_behav.techScore - cand_behav.techScore));
    behav_score = behav_score + (10 - abs(s11_behav.cultureScore - cand_behav.cultureScore));
    
    scores(i) = common_friends*5 + attr_score*3 + behav_score*2;
    reasons{i} = ['commonFriends:' num2str(common_friends) ' attr:' num2str(attr_score) ' behav:' num2str(behav_score)];
end

% TOP3
[~, topIdx] = sort(scores, 'descend');
top3 = nonFriends(topIdx(1:3));

disp(' ');
disp('=== Top 3 Recommended Friends for S11 ===');
for i = 1:3
    disp(['Recommendation #' num2str(i) ': ' char(top3(i)) '   Score = ' num2str(scores(topIdx(i)))]);
    disp(['   Reason: ' reasons{topIdx(i)}]);
end

disp(' ');
disp('=== Why they are not friends yet? (Suggestions) ===');
for i = 1:3
    disp(['• ' char(top3(i)) ': Possibly due to few common friends + slight mismatch in active time/clubs. Suggestion: Introduce via shared club activity or same-topic post.']);
end

% 可视化
h = plot(G, 'Layout','force', 'NodeLabel', string(G.Nodes.Name), 'MarkerSize', 5);
title('S11 and Top 3 Recommended Friends (S11 highlighted in red)');
hold on;

% 高光强调
highlight(h, s11_idx, 'NodeColor','r', 'MarkerSize',12);
highlight(h, find(ismember(string(G.Nodes.Name), top3)), 'NodeColor','y', 'MarkerSize',8);

disp(' ');
disp('Q2 completed successfully!');
disp('Right-click the figure window -> Save As to save the image.');